# routes/entries.py
from flask import request, jsonify
from datetime import datetime, date as date_cls, timedelta
from models import Entry, Site, db
from utils.helpers import generate_id, calculate_daily_overhead
from utils.auto_entry import compute_auto_entries
from routes import entries_bp


# ======================================================================
# GET /api/entries
# Returns a merged list:
#   - manual / overridden rows from the DB (authoritative)
#   - auto-computed rows for (date, site) combinations without a manual row
#
# Query params:
#   siteId      — optional
#   month       — optional YYYY-MM
#   dateFrom    — optional YYYY-MM-DD
#   dateTo      — optional YYYY-MM-DD
#   includeAuto — 'true' (default) | 'false'
# ======================================================================
@entries_bp.route('', methods=['GET'])
def get_entries():
    try:
        site_id = request.args.get('siteId')
        month = request.args.get('month')
        date_from = request.args.get('dateFrom')
        date_to = request.args.get('dateTo')
        include_auto = request.args.get('includeAuto', 'true').lower() != 'false'

        # -------- Manual entries --------
        query = Entry.query
        if site_id:
            query = query.filter_by(site_id=site_id)
        if date_from:
            query = query.filter(Entry.date >= date_from)
        if date_to:
            query = query.filter(Entry.date <= date_to)
        if month and not date_from and not date_to:
            query = query.filter(Entry.date.like(f'{month}%'))

        manual_entries = query.order_by(Entry.date.desc()).all()
        manual_map = {(e.date.isoformat(), e.site_id): e for e in manual_entries}

        result = [e.to_dict() for e in manual_entries]

        # -------- Auto entries --------
        if include_auto:
            # Determine the range to auto-compute
            if date_from:
                start = datetime.strptime(date_from, '%Y-%m-%d').date()
            elif month:
                start = datetime.strptime(f'{month}-01', '%Y-%m-%d').date()
            else:
                start = date_cls.today() - timedelta(days=30)

            if date_to:
                end = datetime.strptime(date_to, '%Y-%m-%d').date()
            elif month:
                import calendar
                y, m = [int(x) for x in month.split('-')]
                end = date_cls(y, m, calendar.monthrange(y, m)[1])
            else:
                end = date_cls.today()

            # Cap absurd ranges
            if (end - start).days > 366:
                end = start + timedelta(days=366)

            current = start
            while current <= end:
                try:
                    auto_rows = compute_auto_entries(current.isoformat(), site_id=site_id)
                except Exception as inner:
                    print(f"compute_auto_entries failed for {current}: {inner}")
                    auto_rows = []

                for row in auto_rows:
                    key = (row['date'], row['siteId'])
                    if key not in manual_map:
                        # Give auto rows a stable synthetic id
                        row['id'] = f"auto-{row['siteId']}-{row['date']}"
                        result.append(row)
                current += timedelta(days=1)

            # Sort merged list: newest first, then by site name
            result.sort(
                key=lambda r: (r.get('date') or '', r.get('siteName') or ''),
                reverse=True,
            )

        return jsonify(result), 200

    except Exception as e:
        print(f"Error in get_entries: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ======================================================================
# GET /api/entries/auto?date=YYYY-MM-DD&siteId=...
# Raw auto rows (no DB merge). Useful for the Override dialog preview.
# ======================================================================
@entries_bp.route('/auto', methods=['GET'])
def get_auto_entries():
    try:
        date_str = request.args.get('date')
        site_id = request.args.get('siteId')
        if not date_str:
            return jsonify({'error': 'date parameter is required'}), 400
        rows = compute_auto_entries(date_str, site_id=site_id)
        return jsonify(rows), 200
    except Exception as e:
        print(f"Error in get_auto_entries: {str(e)}")
        return jsonify({'error': str(e)}), 500


# ======================================================================
# POST /api/entries — Create or upsert (manual override)
# If an entry already exists for (date, site), it's updated in place and
# marked manual_override = true. Otherwise a new one is created.
# ======================================================================
@entries_bp.route('', methods=['POST'])
def create_entry():
    try:
        data = request.json
        entry_date = datetime.strptime(data.get('date'), '%Y-%m-%d').date()
        site_id = data.get('siteId')
        if not site_id:
            return jsonify({'error': 'siteId is required'}), 400

        month_key = entry_date.strftime('%Y-%m')

        # Overhead: use sent value if present, else compute
        if 'overhead' in data and data['overhead'] is not None:
            overhead = float(data['overhead'])
        else:
            overhead = float(calculate_daily_overhead(month_key, site_id) or 0)

        manual_override = bool(data.get('manualOverride', True))

        existing = Entry.query.filter_by(date=entry_date, site_id=site_id).first()

        if existing:
            entry = existing
            entry.kamai = float(data.get('kamai', 0))
            entry.labour = float(data.get('labour', 0))
            entry.overhead = overhead
            entry.one_time = float(data.get('oneTime', 0))
            entry.material_cost = float(data.get('materialCost', 0))
            entry.equipment_cost = float(data.get('equipmentCost', 0))
            entry.transport_cost = float(data.get('transportCost', 0))
            entry.other_expense = float(data.get('otherExpense', 0))
            entry.note = data.get('note', '')
            entry.source = 'mixed' if manual_override else 'manual'
            entry.manual_override = manual_override
        else:
            entry = Entry(
                id=generate_id(),
                date=entry_date,
                site_id=site_id,
                kamai=float(data.get('kamai', 0)),
                labour=float(data.get('labour', 0)),
                overhead=overhead,
                one_time=float(data.get('oneTime', 0)),
                material_cost=float(data.get('materialCost', 0)),
                equipment_cost=float(data.get('equipmentCost', 0)),
                transport_cost=float(data.get('transportCost', 0)),
                other_expense=float(data.get('otherExpense', 0)),
                note=data.get('note', ''),
                source='manual',
                manual_override=manual_override,
            )
            db.session.add(entry)

        # Snapshot the auto values at this moment (for UI comparison)
        try:
            auto_rows = compute_auto_entries(entry_date.isoformat(), site_id=site_id)
            if auto_rows:
                ar = auto_rows[0]
                entry.auto_kamai = ar.get('kamai', 0)
                entry.auto_labour = ar.get('labour', 0)
                entry.auto_overhead = ar.get('overhead', 0)
                entry.auto_one_time = ar.get('oneTime', 0)
        except Exception as inner:
            print(f"Snapshot auto failed: {inner}")

        entry.calculate_profit()
        db.session.commit()
        return jsonify(entry.to_dict()), 201

    except Exception as e:
        db.session.rollback()
        print(f"Error in create_entry: {str(e)}")
        return jsonify({'error': str(e)}), 400


@entries_bp.route('/<entry_id>', methods=['GET'])
def get_entry(entry_id):
    try:
        entry = Entry.query.get_or_404(entry_id)
        return jsonify(entry.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)}), 404


@entries_bp.route('/<entry_id>', methods=['PUT'])
def update_entry(entry_id):
    try:
        entry = Entry.query.get_or_404(entry_id)
        data = request.json

        if 'kamai' in data:
            entry.kamai = float(data['kamai'])
        if 'labour' in data:
            entry.labour = float(data['labour'])
        if 'overhead' in data:
            entry.overhead = float(data['overhead'])
        if 'oneTime' in data:
            entry.one_time = float(data['oneTime'])
        if 'materialCost' in data:
            entry.material_cost = float(data['materialCost'])
        if 'equipmentCost' in data:
            entry.equipment_cost = float(data['equipmentCost'])
        if 'transportCost' in data:
            entry.transport_cost = float(data['transportCost'])
        if 'otherExpense' in data:
            entry.other_expense = float(data['otherExpense'])
        if 'note' in data:
            entry.note = data['note']

        entry.source = 'mixed'
        entry.manual_override = True
        entry.calculate_profit()

        db.session.commit()
        return jsonify(entry.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


# ======================================================================
# DELETE — also used to "revert to auto".
# After deletion, the GET handler will start returning the auto row again.
# ======================================================================
@entries_bp.route('/<entry_id>', methods=['DELETE'])
def delete_entry(entry_id):
    try:
        entry = Entry.query.get_or_404(entry_id)
        db.session.delete(entry)
        db.session.commit()
        return jsonify({'message': 'Entry deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


@entries_bp.route('/summary/monthly', methods=['GET'])
def get_monthly_entry_summary():
    try:
        month = request.args.get('month')
        site_id = request.args.get('siteId')
        if not month:
            return jsonify({'error': 'Month parameter is required'}), 400
        summary = Entry.get_monthly_summary(month, site_id)
        return jsonify(summary)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
# utils/cors.py - Complete CORS handling
from flask import request, jsonify

def handle_options(app):
    """Handle CORS preflight requests properly"""
    
    @app.after_request
    def after_request(response):
        """Add CORS headers to every response"""
        origin = request.headers.get('Origin')
        
        # Allow all origins in development
        if origin:
            response.headers['Access-Control-Allow-Origin'] = origin
        else:
            response.headers['Access-Control-Allow-Origin'] = '*'
        
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, Accept, Origin, X-Requested-With, Content-Disposition'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS, PATCH'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Access-Control-Max-Age'] = '86400'
        
        return response
    
    @app.route('/api/<path:path>', methods=['OPTIONS'])
    @app.route('/<path:path>', methods=['OPTIONS'])
    def handle_options_request(path):
        """Handle preflight OPTIONS requests"""
        response = jsonify({'status': 'OK'})
        origin = request.headers.get('Origin')
        
        if origin:
            response.headers['Access-Control-Allow-Origin'] = origin
        else:
            response.headers['Access-Control-Allow-Origin'] = '*'
        
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, Accept, Origin, X-Requested-With, Content-Disposition'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS, PATCH'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Access-Control-Max-Age'] = '86400'
        
        return response
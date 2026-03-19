"""
routes/offline.py — Low Data Mode toggle & status
"""
from flask import Blueprint, jsonify, request
from flask_login import login_required
from utils.cache_manager import set_low_data_mode, is_low_bandwidth, get_cache

offline_bp = Blueprint('offline', __name__, url_prefix='/offline')


@offline_bp.route('/status')
@login_required
def status():
    return jsonify({
        'low_bandwidth': is_low_bandwidth(),
        'low_data_forced': bool(get_cache('low_data_mode_forced')),
    })


@offline_bp.route('/set-mode', methods=['POST'])
@login_required
def set_mode():
    enabled = request.json.get('enabled', False)
    set_low_data_mode(bool(enabled))
    return jsonify({'ok': True, 'low_data_mode': bool(enabled)})

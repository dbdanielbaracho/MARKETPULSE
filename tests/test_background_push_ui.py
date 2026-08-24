from fastapi.testclient import TestClient

from app.entrypoint import app


client = TestClient(app)


def test_alert_page_exposes_explicit_background_push_opt_in():
    response = client.get('/alerts')
    assert response.status_code == 200
    for marker in (
        'id="background-push-panel"',
        'id="enable-background-push"',
        'id="disable-background-push"',
        '/api/v1/push/config',
        'PushManager',
        'Notification.requestPermission()',
        "applicationServerKey:base64UrlToUint8Array(pushServerConfig.public_key)",
        'X-PrediBeacon-Push-Token',
    ):
        assert marker in response.text
    assert 'not forecasts or trading recommendations' in response.text


def test_service_worker_handles_push_and_click_with_same_origin_navigation():
    response = client.get('/service-worker.js')
    assert response.status_code == 200
    script = response.text
    assert "addEventListener('push'" in script
    assert 'showNotification' in script
    assert "addEventListener('notificationclick'" in script
    assert 'candidate.origin===self.location.origin' in script
    assert "clients.openWindow(target)" in script
    assert "const CACHE='predibeacon-v4'" in script

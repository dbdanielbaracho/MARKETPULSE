from app.services.alert_page_enhancements import enhance_alerts_template


def _base() -> str:
    return """<style></style><section class=\"panel\"><h2>Saved alerts</h2></section><script>async function check(){if('Notification'in window&&Notification.permission==='granted')new Notification('PrediBeacon market alert',{body:m.title+' reached '+p+'%'})}document.querySelector('#add').addEventListener('click',add);</script>"""


def test_alert_enhancement_adds_evidence_and_configurable_closing_signals():
    result = enhance_alerts_template(_base())
    assert 'id="smart-evidence"' in result
    assert 'id="smart-closing"' in result
    assert 'id="smart-closing-hours"' in result
    assert 'latest_evidence_key' in result
    assert 'closing.remaining_hours' in result
    assert 'closingHours>closingHours' in result


def test_alert_enhancement_prefers_service_worker_notifications_for_mobile():
    result = enhance_alerts_template(_base())
    assert 'registration.showNotification' in result
    assert "Notification.requestPermission()" in result
    assert "document.visibilityState==='visible'" in result
    assert 'Durable background push is not enabled.' in result


def test_existing_probability_notification_is_upgraded_to_same_safe_delivery_helper():
    result = enhance_alerts_template(_base())
    assert "await smartNotify('PrediBeacon market alert',m.title+' reached '+p+'%')" in result
    assert "new Notification('PrediBeacon market alert'" not in result


def test_enhancement_fails_closed_if_expected_template_anchors_change():
    source = '<html><body>unexpected template</body></html>'
    assert enhance_alerts_template(source) == source

import 'package:flutter_test/flutter_test.dart';
import 'package:mobile_app/services/reminder_notification_service.dart';

void main() {
  test('reminderIdFromPayload parses json payload', () {
    final id = ReminderNotificationService.reminderIdFromPayload(
      '{"reminder_id":"abc-123"}',
    );
    expect(id, 'abc-123');
  });
}

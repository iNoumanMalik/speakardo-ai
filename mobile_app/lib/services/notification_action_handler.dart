import 'package:flutter/foundation.dart';

import 'api_service.dart';
import 'reminder_notification_service.dart';

/// Handles Done / Snooze actions from reminder notifications.
class NotificationActionHandler {
  NotificationActionHandler._();

  static final ApiService _api = ApiService();

  /// Optional hook to refresh in-app reminder list after an action.
  static void Function()? onRemindersChanged;

  static const actionDone = 'action_done';
  static const actionSnooze5 = 'action_snooze_5';
  static const actionSnooze10 = 'action_snooze_10';
  static const actionSnooze30 = 'action_snooze_30';

  static Future<void> processAction({
    required String? actionId,
    required String? reminderId,
  }) async {
    if (actionId == null || actionId.isEmpty) {
      debugPrint('NotificationActionHandler: actionId required');
      return;
    }

    if (reminderId == null || reminderId.isEmpty) {
      debugPrint('Notification action missing reminder_id for action=$actionId');
      return;
    }

    debugPrint('Notification action=$actionId reminder_id=$reminderId');

    try {
      switch (actionId) {
        case actionDone:
          await _api.completeReminder(reminderId);
          await ReminderNotificationService.cancelReminderNotification(reminderId);
          debugPrint('Reminder marked done from notification: $reminderId');
          break;
        case actionSnooze5:
          await _snooze(reminderId, 5);
          break;
        case actionSnooze10:
          await _snooze(reminderId, 10);
          break;
        case actionSnooze30:
          await _snooze(reminderId, 30);
          break;
        default:
          debugPrint('Unknown notification action: $actionId');
          return;
      }
      onRemindersChanged?.call();
    } catch (e, stack) {
      debugPrint('Notification action failed action=$actionId: $e\n$stack');
    }
  }

  static Future<void> _snooze(String id, int minutes) async {
    debugPrint('Snooze requested reminder_id=$id minutes=$minutes');
    await _api.snoozeReminder(id, minutes);
    await ReminderNotificationService.cancelReminderNotification(id);
    debugPrint(
      'Snooze saved reminder_id=$id — next fire in $minutes minutes (server UTC)',
    );
  }
}

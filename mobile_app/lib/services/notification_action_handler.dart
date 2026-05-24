import 'dart:async';

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
    if (reminderId == null || reminderId.isEmpty) {
      debugPrint('Notification action missing reminder_id');
      return;
    }

    final id = reminderId;
    try {
      switch (actionId) {
        case actionDone:
          await _api.completeReminder(id);
          await ReminderNotificationService.cancelReminderNotification(id);
          debugPrint('Reminder marked done from notification: $id');
        case actionSnooze5:
          await _snooze(id, 5);
        case actionSnooze10:
          await _snooze(id, 10);
        case actionSnooze30:
          await _snooze(id, 30);
        default:
          debugPrint('Unknown notification action: $actionId');
          return;
      }
      onRemindersChanged?.call();
    } catch (e) {
      debugPrint('Notification action failed: $e');
    }
  }

  static Future<void> _snooze(String id, int minutes) async {
    await _api.snoozeReminder(id, minutes);
    await ReminderNotificationService.cancelReminderNotification(id);
    debugPrint('Reminder snoozed ${minutes}m from notification: $id');
  }
}

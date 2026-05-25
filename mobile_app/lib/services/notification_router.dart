import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

import 'notification_action_handler.dart';
import 'notification_deep_link.dart';
import 'reminder_notification_service.dart';

/// Routes local notification taps: body tap → deep link; action → Done/Snooze.
class NotificationRouter {
  NotificationRouter._();

  static Future<void> handleResponse(NotificationResponse response) async {
    final reminderId =
        ReminderNotificationService.reminderIdFromPayload(response.payload);
    if (reminderId == null || reminderId.isEmpty) {
      debugPrint('NotificationRouter: missing reminder_id in payload');
      return;
    }

    final actionId = response.actionId;
    if (actionId == null || actionId.isEmpty) {
      debugPrint('NotificationRouter: tap open reminder_id=$reminderId');
      NotificationDeepLink.requestOpen(reminderId);
      return;
    }

    await NotificationActionHandler.processAction(
      actionId: actionId,
      reminderId: reminderId,
    );
  }

  static void handleFcmData(Map<String, dynamic> data) {
    if (data['type'] != 'reminder_due' && data['reminder_id'] == null) {
      return;
    }
    final reminderId = data['reminder_id']?.toString();
    if (reminderId == null || reminderId.isEmpty) return;
    debugPrint('NotificationRouter: FCM open reminder_id=$reminderId');
    NotificationDeepLink.requestOpen(reminderId);
  }
}

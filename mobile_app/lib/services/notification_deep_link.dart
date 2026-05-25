import 'package:flutter/foundation.dart';

/// Opens a specific reminder in the Reminders tab (from notification tap / FCM).
class NotificationDeepLink {
  NotificationDeepLink._();

  static String? _pendingReminderId;

  /// Set from [MainScreen] when the reminders list is ready to navigate.
  static void Function(String reminderId)? onOpenReminder;

  static String? get pendingReminderId => _pendingReminderId;

  static void requestOpen(String reminderId) {
    final id = reminderId.trim();
    if (id.isEmpty) return;
    _pendingReminderId = id;
    debugPrint('NotificationDeepLink: request open reminder_id=$id');
    final handler = onOpenReminder;
    if (handler != null) {
      _pendingReminderId = null;
      handler(id);
    }
  }

  /// Call when [MainScreen] mounts so a pending id from cold start is handled.
  static void consumePending() {
    final id = _pendingReminderId;
    if (id == null) return;
    final handler = onOpenReminder;
    if (handler == null) return;
    _pendingReminderId = null;
    handler(id);
  }

  static void clear() {
    _pendingReminderId = null;
  }
}

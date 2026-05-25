import 'dart:async';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

import 'notification_router.dart';
import 'reminder_notification_service.dart';

/// FCM messages while app is in background/terminated.
@pragma('vm:entry-point')
Future<void> firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp();
  await ReminderNotificationService.ensureInitialized();
  await ReminderNotificationService.handleRemoteMessage(message);
}

/// Notification action taps (Done / Snooze) while app is in background/terminated.
@pragma('vm:entry-point')
void onBackgroundNotificationResponse(NotificationResponse response) {
  WidgetsFlutterBinding.ensureInitialized();
  unawaited(_handleBackgroundNotificationAction(response));
}

Future<void> _handleBackgroundNotificationAction(
  NotificationResponse response,
) async {
  await ReminderNotificationService.ensureInitialized();
  await NotificationRouter.handleResponse(response);
}

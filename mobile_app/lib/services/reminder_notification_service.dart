import 'dart:async';
import 'dart:convert';

import 'package:flutter/widgets.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:firebase_messaging/firebase_messaging.dart';

import 'notification_action_handler.dart';

/// Shows reminder alerts with Done / Snooze actions (local notifications).
class ReminderNotificationService {
  ReminderNotificationService._();

  static const String channelId = 'high_importance_channel';
  static const String channelName = 'High Importance Notifications';
  static const String channelDescription = 'Reminder alerts';
  static const String iosCategoryId = 'reminder_actions';

  static final FlutterLocalNotificationsPlugin _plugin =
      FlutterLocalNotificationsPlugin();

  static bool _initialized = false;

  static Future<void> ensureInitialized() async {
    if (_initialized) return;

    const androidChannel = AndroidNotificationChannel(
      channelId,
      channelName,
      description: channelDescription,
      importance: Importance.max,
    );

    final iosCategories = <DarwinNotificationCategory>[
      DarwinNotificationCategory(
        iosCategoryId,
        actions: <DarwinNotificationAction>[
          DarwinNotificationAction.plain(
            NotificationActionHandler.actionDone,
            'Done',
            options: {DarwinNotificationActionOption.foreground},
          ),
          DarwinNotificationAction.plain(
            NotificationActionHandler.actionSnooze5,
            'Snooze 5m',
          ),
          DarwinNotificationAction.plain(
            NotificationActionHandler.actionSnooze10,
            'Snooze 10m',
          ),
        ],
      ),
    ];

    final settings = InitializationSettings(
      android: const AndroidInitializationSettings('@mipmap/ic_launcher'),
      iOS: DarwinInitializationSettings(
        notificationCategories: iosCategories,
      ),
    );

    await _plugin.initialize(
      settings,
      onDidReceiveNotificationResponse: _onForegroundNotificationResponse,
      onDidReceiveBackgroundNotificationResponse:
          onBackgroundNotificationResponse,
    );

    await _plugin
        .resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin>()
        ?.createNotificationChannel(androidChannel);

    _initialized = true;
  }

  static void _onForegroundNotificationResponse(NotificationResponse response) {
    unawaited(_dispatchAction(response));
  }

  static Future<void> _dispatchAction(NotificationResponse response) async {
    await NotificationActionHandler.processAction(
      actionId: response.actionId,
      reminderId: reminderIdFromPayload(response.payload),
    );
  }

  @visibleForTesting
  static String? reminderIdFromPayload(String? payload) {
    if (payload == null || payload.isEmpty) return null;
    try {
      final decoded = jsonDecode(payload) as Map<String, dynamic>;
      return decoded['reminder_id']?.toString();
    } catch (_) {
      return payload;
    }
  }

  static int notificationIdFor(String reminderId) {
    return reminderId.hashCode.abs() % 2147483647;
  }

  static Future<void> cancelReminderNotification(String reminderId) async {
    await ensureInitialized();
    await _plugin.cancel(notificationIdFor(reminderId));
  }

  static Future<void> showReminderNotification({
    required String reminderId,
    required String title,
    required String body,
  }) async {
    await ensureInitialized();

    final payload = jsonEncode({'reminder_id': reminderId});
    final notificationId = notificationIdFor(reminderId);

    const androidActions = <AndroidNotificationAction>[
      AndroidNotificationAction(
        NotificationActionHandler.actionDone,
        'Done',
        showsUserInterface: true,
        cancelNotification: true,
      ),
      AndroidNotificationAction(
        NotificationActionHandler.actionSnooze5,
        'Snooze 5m',
        cancelNotification: true,
      ),
      AndroidNotificationAction(
        NotificationActionHandler.actionSnooze10,
        'Snooze 10m',
        cancelNotification: true,
      ),
      AndroidNotificationAction(
        NotificationActionHandler.actionSnooze30,
        'Snooze 30m',
        cancelNotification: true,
      ),
    ];

    final androidDetails = AndroidNotificationDetails(
      channelId,
      channelName,
      channelDescription: channelDescription,
      importance: Importance.max,
      priority: Priority.high,
      playSound: true,
      category: AndroidNotificationCategory.reminder,
      actions: androidActions,
    );

    const iosDetails = DarwinNotificationDetails(
      categoryIdentifier: iosCategoryId,
      presentAlert: true,
      presentSound: true,
    );

    await _plugin.show(
      notificationId,
      title,
      body,
      NotificationDetails(
        android: androidDetails,
        iOS: iosDetails,
      ),
      payload: payload,
    );
  }

  static Future<void> handleRemoteMessage(RemoteMessage message) async {
    final data = message.data;
    if (data['type'] != 'reminder_due' && data['reminder_id'] == null) {
      return;
    }

    final reminderId = data['reminder_id']?.toString();
    if (reminderId == null || reminderId.isEmpty) {
      return;
    }

    final task = data['task']?.toString() ??
        message.notification?.body ??
        'You have a reminder';

    await showReminderNotification(
      reminderId: reminderId,
      title: message.notification?.title ?? 'Reminder',
      body: task,
    );
  }
}

/// Notification action taps while app is terminated/backgrounded.
@pragma('vm:entry-point')
void onBackgroundNotificationResponse(NotificationResponse response) {
  WidgetsFlutterBinding.ensureInitialized();
  unawaited(_backgroundNotificationAction(response));
}

Future<void> _backgroundNotificationAction(
  NotificationResponse response,
) async {
  await ReminderNotificationService.ensureInitialized();
  await NotificationActionHandler.processAction(
    actionId: response.actionId,
    reminderId: ReminderNotificationService.reminderIdFromPayload(
      response.payload,
    ),
  );
}

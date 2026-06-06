import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'chat_screen.dart';
import 'profile_screen.dart';
import 'reminders_screen.dart';
import '../services/notification_action_handler.dart';
import '../services/notification_deep_link.dart';
import '../services/device_timezone_service.dart';
import '../services/profile_provider.dart';
import '../services/reminder_provider.dart';

class MainScreen extends StatefulWidget {
  const MainScreen({super.key});

  @override
  State<MainScreen> createState() => _MainScreenState();
}

class _MainScreenState extends State<MainScreen> with WidgetsBindingObserver {
  late int _selectedIndex;
  final GlobalKey<RemindersScreenState> _remindersKey =
      GlobalKey<RemindersScreenState>();

  @override
  void initState() {
    super.initState();
    // Open Reminders tab first when app was launched from a notification body tap.
    _selectedIndex = NotificationDeepLink.hasPending ? 1 : 0;
    WidgetsBinding.instance.addObserver(this);

    NotificationActionHandler.onRemindersChanged = () {
      if (!mounted) return;
      context.read<ReminderProvider>().fetchReminders();
    };
    NotificationDeepLink.onOpenReminder = _openReminderFromNotification;

    WidgetsBinding.instance.addPostFrameCallback((_) {
      unawaited(_consumeNotificationDeepLink());
      unawaited(_syncDeviceTimezone());
    });
  }

  Future<void> _syncDeviceTimezone() async {
    if (!mounted) return;
    final provider = context.read<ProfileProvider>();
    await provider.fetchProfile();
    if (!mounted) return;
    final before = provider.profile?.timezone;
    final updated = await DeviceTimezoneService.syncIfNeeded(before);
    if (!mounted) return;
    if (updated) {
      await provider.fetchProfile();
    }
  }

  Future<void> _consumeNotificationDeepLink() async {
    await NotificationDeepLink.loadFromDisk();
    if (!mounted) return;
    if (NotificationDeepLink.hasPending && _selectedIndex != 1) {
      setState(() => _selectedIndex = 1);
    }
    await NotificationDeepLink.consumePending();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    NotificationActionHandler.onRemindersChanged = null;
    NotificationDeepLink.onOpenReminder = null;
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      unawaited(_consumeNotificationDeepLink());
      unawaited(_syncDeviceTimezone());
    }
  }

  void _openReminderFromNotification(String reminderId) {
    if (!mounted) return;

    void navigate() {
      if (!mounted) return;
      setState(() => _selectedIndex = 1);
      context.read<ReminderProvider>().openReminderInList(reminderId).then((_) {
        if (!mounted) return;
        _remindersKey.currentState?.scrollToReminder(reminderId);
      });
    }

    navigate();
    WidgetsBinding.instance.addPostFrameCallback((_) => navigate());
  }

  List<Widget> get _screens => [
        const ChatScreen(),
        RemindersScreen(key: _remindersKey),
        const ProfileScreen(),
      ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _selectedIndex,
        children: _screens,
      ),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _selectedIndex,
        type: BottomNavigationBarType.fixed,
        onTap: (index) {
          setState(() {
            _selectedIndex = index;
          });

          if (index == 1) {
            context.read<ReminderProvider>().fetchReminders();
          } else if (index == 2) {
            context.read<ProfileProvider>().fetchProfile();
          }
        },
        items: const [
          BottomNavigationBarItem(
            icon: Icon(Icons.chat_bubble_outline),
            activeIcon: Icon(Icons.chat_bubble),
            label: 'Chat',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.list_alt_outlined),
            activeIcon: Icon(Icons.list_alt),
            label: 'Reminders',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.person_outline),
            activeIcon: Icon(Icons.person),
            label: 'Profile',
          ),
        ],
        selectedItemColor: const Color(0xFF6750A4),
      ),
    );
  }
}

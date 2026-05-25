import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'chat_screen.dart';
import 'profile_screen.dart';
import 'reminders_screen.dart';
import '../services/notification_action_handler.dart';
import '../services/notification_deep_link.dart';
import '../services/profile_provider.dart';
import '../services/reminder_provider.dart';

class MainScreen extends StatefulWidget {
  const MainScreen({super.key});

  @override
  State<MainScreen> createState() => _MainScreenState();
}

class _MainScreenState extends State<MainScreen> {
  int _selectedIndex = 0;
  final GlobalKey<RemindersScreenState> _remindersKey =
      GlobalKey<RemindersScreenState>();

  @override
  void initState() {
    super.initState();
    NotificationActionHandler.onRemindersChanged = () {
      if (!mounted) return;
      context.read<ReminderProvider>().fetchReminders();
    };
    NotificationDeepLink.onOpenReminder = _openReminderFromNotification;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      NotificationDeepLink.consumePending();
    });
  }

  @override
  void dispose() {
    NotificationActionHandler.onRemindersChanged = null;
    NotificationDeepLink.onOpenReminder = null;
    super.dispose();
  }

  void _openReminderFromNotification(String reminderId) {
    if (!mounted) return;
    setState(() => _selectedIndex = 1);
    context.read<ReminderProvider>().openReminderInList(reminderId).then((_) {
      if (!mounted) return;
      _remindersKey.currentState?.scrollToReminder(reminderId);
    });
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

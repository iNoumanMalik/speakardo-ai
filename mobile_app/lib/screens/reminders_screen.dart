import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/auth_provider.dart';
import '../services/reminder_provider.dart';
import '../widgets/reminder_card.dart';

class RemindersScreen extends StatefulWidget {
  const RemindersScreen({Key? key}) : super(key: key);

  @override
  State<RemindersScreen> createState() => _RemindersScreenState();
}

class _RemindersScreenState extends State<RemindersScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<ReminderProvider>().fetchReminders();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('My Reminders'),
        centerTitle: true,
        actions: [
          IconButton(
            tooltip: 'Sign out',
            icon: const Icon(Icons.logout),
            onPressed: () => context.read<AuthProvider>().logout(),
          ),
        ],
      ),
      body: Consumer<ReminderProvider>(
        builder: (context, provider, child) {
          if (provider.isLoading && provider.reminders.isEmpty) {
            return const Center(child: CircularProgressIndicator());
          }

          if (provider.reminders.isEmpty) {
            return const Center(
              child: Text(
                "No reminders yet.\nTry chat to create one!",
                textAlign: TextAlign.center,
                style: TextStyle(color: Colors.grey, fontSize: 16),
              ),
            );
          }

          return RefreshIndicator(
            onRefresh: provider.fetchReminders,
            child: ListView.builder(
              itemCount: provider.reminders.length,
              itemBuilder: (context, index) {
                final reminder = provider.reminders[index];
                return ReminderCard(
                  reminder: reminder,
                  onComplete: () => provider.completeReminder(reminder.id),
                  onDelete: () => provider.deleteReminder(reminder.id),
                );
              },
            ),
          );
        },
      ),
    );
  }
}

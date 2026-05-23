import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/profile_provider.dart';
import '../services/reminder_provider.dart';
import '../utils/reminder_grouping.dart';
import '../utils/timezone_clock.dart';
import '../widgets/reminder_card.dart';
import '../widgets/reminder_section_header.dart';

class RemindersScreen extends StatefulWidget {
  const RemindersScreen({Key? key}) : super(key: key);

  @override
  State<RemindersScreen> createState() => _RemindersScreenState();
}

class _RemindersScreenState extends State<RemindersScreen> {
  ReminderListFilter _filter = ReminderListFilter.all;

  void _showError(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: Theme.of(context).colorScheme.error,
      ),
    );
  }

  Future<void> _loadReminders() async {
    try {
      await context.read<ReminderProvider>().fetchReminders();
    } catch (_) {
      _showError('Could not load reminders. Pull to refresh to try again.');
    }
  }

  Future<void> _completeReminder(String id) async {
    try {
      await context.read<ReminderProvider>().completeReminder(id);
    } catch (_) {
      _showError('Could not update reminder. Please try again.');
    }
  }

  Future<void> _deleteReminder(String id) async {
    try {
      await context.read<ReminderProvider>().deleteReminder(id);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Reminder deleted')),
      );
    } catch (_) {
      _showError('Could not delete reminder. Please try again.');
    }
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _loadReminders());
  }

  Widget _buildFilterChips() {
    const filters = ReminderListFilter.values;
    const labels = {
      ReminderListFilter.all: 'All',
      ReminderListFilter.today: 'Today',
      ReminderListFilter.tomorrow: 'Tomorrow',
      ReminderListFilter.upcoming: 'Upcoming',
      ReminderListFilter.completed: 'Completed',
    };

    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
      child: Row(
        children: filters.map((filter) {
          final selected = _filter == filter;
          return Padding(
            padding: const EdgeInsets.only(right: 8),
            child: FilterChip(
              label: Text(labels[filter]!),
              selected: selected,
              onSelected: (_) => setState(() => _filter = filter),
              showCheckmark: false,
              selectedColor: const Color(0xFF6750A4).withValues(alpha: 0.2),
              checkmarkColor: const Color(0xFF6750A4),
              labelStyle: TextStyle(
                fontWeight: selected ? FontWeight.w600 : FontWeight.w500,
                color: selected ? const Color(0xFF6750A4) : null,
              ),
            ),
          );
        }).toList(),
      ),
    );
  }

  Widget _buildEmptyState({required bool hasAnyReminders}) {
    final message = hasAnyReminders
        ? emptyMessageForFilter(_filter)
        : emptyMessageForFilter(ReminderListFilter.all);

    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Text(
          message,
          textAlign: TextAlign.center,
          style: TextStyle(
            color: Colors.grey.shade600,
            fontSize: 16,
            height: 1.4,
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('My Reminders'),
        centerTitle: true,
      ),
      body: Consumer2<ReminderProvider, ProfileProvider>(
        builder: (context, provider, profileProvider, child) {
          final clock = clockNowInTimezone(profileProvider.timezone);
          if (provider.isLoading && provider.reminders.isEmpty) {
            return const Center(child: CircularProgressIndicator());
          }

          final hasAnyReminders = provider.reminders.isNotEmpty;
          final sections = buildReminderSections(
            provider.reminders,
            _filter,
            now: clock,
          );

          if (!hasAnyReminders) {
            return Column(
              children: [
                _buildFilterChips(),
                Expanded(child: _buildEmptyState(hasAnyReminders: false)),
              ],
            );
          }

          if (sections.isEmpty) {
            return Column(
              children: [
                _buildFilterChips(),
                Expanded(child: _buildEmptyState(hasAnyReminders: true)),
              ],
            );
          }

          return RefreshIndicator(
            onRefresh: _loadReminders,
            child: CustomScrollView(
              slivers: [
                SliverToBoxAdapter(child: _buildFilterChips()),
                for (final section in sections) ...[
                  SliverToBoxAdapter(
                    child: ReminderSectionHeader(section: section),
                  ),
                  SliverList(
                    delegate: SliverChildBuilderDelegate(
                      (context, index) {
                        final reminder = section.reminders[index];
                        return ReminderCard(
                          reminder: reminder,
                          clock: clock,
                          onComplete: () => _completeReminder(reminder.id),
                          onDelete: () => _deleteReminder(reminder.id),
                        );
                      },
                      childCount: section.reminders.length,
                    ),
                  ),
                ],
                const SliverToBoxAdapter(child: SizedBox(height: 16)),
              ],
            ),
          );
        },
      ),
    );
  }
}

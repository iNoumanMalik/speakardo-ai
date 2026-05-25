import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/reminder_provider.dart';
import '../utils/reminder_grouping.dart';
import '../models/reminder.dart';
import '../widgets/reminder_card.dart';
import '../widgets/reminder_edit_sheet.dart';
import '../widgets/reminder_section_header.dart';

class RemindersScreen extends StatefulWidget {
  const RemindersScreen({super.key});

  @override
  State<RemindersScreen> createState() => RemindersScreenState();
}

class RemindersScreenState extends State<RemindersScreen> {
  ReminderListFilter _filter = ReminderListFilter.all;
  final ScrollController _scrollController = ScrollController();
  final Map<String, GlobalKey> _reminderKeys = {};

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

  Future<void> _editReminder(Reminder reminder) async {
    final payload = await ReminderEditSheet.show(
      context,
      reminder: reminder,
      title: 'Edit reminder',
      submitLabel: 'Save changes',
    );
    if (payload == null || !mounted) return;

    try {
      await context.read<ReminderProvider>().updateReminder(
            reminder.id,
            task: payload['task'] as String,
            localDateTime: DateTime.parse(payload['datetime'] as String).toLocal(),
            repeat: payload['repeat'] as String?,
          );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Reminder updated')),
      );
    } catch (e) {
      _showError(e.toString());
    }
  }

  Future<void> _republishReminder(Reminder reminder) async {
    final needsNewTime = !reminder.datetime.isAfter(DateTime.now());
    final payload = await ReminderEditSheet.show(
      context,
      reminder: reminder,
      title: 'Republish reminder',
      submitLabel: 'Republish',
      defaultToNextHour: needsNewTime,
    );
    if (payload == null || !mounted) return;

    try {
      await context.read<ReminderProvider>().republishReminder(
            reminder.id,
            task: payload['task'] as String,
            localDateTime:
                DateTime.parse(payload['datetime'] as String).toLocal(),
            repeat: payload['repeat'] as String?,
          );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Reminder republished')),
      );
    } catch (e) {
      _showError(e.toString());
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

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  GlobalKey _keyForReminder(String id) =>
      _reminderKeys.putIfAbsent(id, () => GlobalKey());

  void scrollToReminder(String reminderId) {
    final provider = context.read<ReminderProvider>();
    Reminder? reminder;
    for (final r in provider.reminders) {
      if (r.id == reminderId) {
        reminder = r;
        break;
      }
    }
    if (reminder != null) {
      final nextFilter = suggestedFilterFor(reminder, DateTime.now());
      if (_filter != nextFilter) {
        setState(() => _filter = nextFilter);
      }
    }
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      final key = _reminderKeys[reminderId];
      final ctx = key?.currentContext;
      if (ctx != null) {
        Scrollable.ensureVisible(
          ctx,
          duration: const Duration(milliseconds: 400),
          curve: Curves.easeInOut,
          alignment: 0.15,
        );
      }
      Future.delayed(const Duration(seconds: 4), () {
        if (mounted) provider.clearHighlight();
      });
    });
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
      body: Consumer<ReminderProvider>(
        builder: (context, provider, child) {
          // Option A: use device local time for grouping (not profile timezone).
          final clock = DateTime.now();
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

          final highlightId = provider.highlightReminderId;

          return RefreshIndicator(
            onRefresh: _loadReminders,
            child: CustomScrollView(
              controller: _scrollController,
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
                        return KeyedSubtree(
                          key: _keyForReminder(reminder.id),
                          child: ReminderCard(
                            reminder: reminder,
                            clock: clock,
                            highlighted: highlightId == reminder.id,
                            onComplete: () => _completeReminder(reminder.id),
                            onEdit: () => _editReminder(reminder),
                            onRepublish: reminder.canRepublish
                                ? () => _republishReminder(reminder)
                                : null,
                            onDelete: () => _deleteReminder(reminder.id),
                          ),
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

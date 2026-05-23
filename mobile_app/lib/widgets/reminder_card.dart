import 'package:flutter/material.dart';
import '../models/reminder.dart';
import '../utils/reminder_grouping.dart';

class ReminderCard extends StatelessWidget {
  final Reminder reminder;
  final DateTime clock;
  final VoidCallback onComplete;
  final VoidCallback onDelete;

  const ReminderCard({
    Key? key,
    required this.reminder,
    required this.clock,
    required this.onComplete,
    required this.onDelete,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final overdue = isReminderOverdue(reminder, clock);
    final scheduleLabel = formatReminderSchedule(reminder, clock);

    return Card(
      margin: const EdgeInsets.symmetric(vertical: 6, horizontal: 16),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(15)),
      elevation: 2,
      clipBehavior: Clip.antiAlias,
      child: IntrinsicHeight(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (overdue)
              Container(
                width: 4,
                color: theme.colorScheme.error,
              ),
            Expanded(
              child: ListTile(
                leading: IconButton(
                  icon: Icon(
                    reminder.isCompleted
                        ? Icons.check_circle
                        : Icons.radio_button_unchecked,
                    color: reminder.isCompleted ? Colors.green : Colors.grey,
                  ),
                  onPressed: reminder.isCompleted ? null : onComplete,
                ),
                title: Text(
                  reminder.displayTask,
                  style: TextStyle(
                    decoration:
                        reminder.isCompleted ? TextDecoration.lineThrough : null,
                    fontWeight: FontWeight.bold,
                    color: reminder.isCompleted
                        ? theme.colorScheme.onSurface.withValues(alpha: 0.6)
                        : null,
                  ),
                ),
                subtitle: Text(
                  scheduleLabel,
                  style: TextStyle(
                    color: overdue
                        ? theme.colorScheme.error
                        : theme.colorScheme.onSurfaceVariant,
                    fontWeight: overdue ? FontWeight.w600 : null,
                  ),
                ),
                trailing: IconButton(
                  icon: const Icon(Icons.delete_outline, color: Colors.redAccent),
                  onPressed: onDelete,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

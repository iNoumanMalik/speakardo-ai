import 'package:flutter_test/flutter_test.dart';
import 'package:mobile_app/models/reminder.dart';
import 'package:mobile_app/utils/reminder_grouping.dart';

Reminder _reminder({
  required String id,
  required DateTime datetime,
  String status = 'pending',
}) {
  return Reminder(
    id: id,
    task: 'Task $id',
    datetime: datetime,
    status: status,
  );
}

void main() {
  final now = DateTime(2026, 5, 23, 14, 0);

  test('groups reminders into today, tomorrow, and upcoming', () {
    final reminders = [
      _reminder(id: '1', datetime: DateTime(2026, 5, 23, 9, 0)),
      _reminder(id: '2', datetime: DateTime(2026, 5, 24, 9, 0)),
      _reminder(id: '3', datetime: DateTime(2026, 5, 30, 9, 0)),
    ];

    final sections = buildReminderSections(
      reminders,
      ReminderListFilter.all,
      now: now,
    );

    expect(sections.length, 3);
    expect(sections[0].bucket, ReminderDateBucket.today);
    expect(sections[1].bucket, ReminderDateBucket.tomorrow);
    expect(sections[2].bucket, ReminderDateBucket.upcoming);
  });

  test('puts past incomplete reminders in overdue section', () {
    final reminders = [
      _reminder(id: '1', datetime: DateTime(2026, 5, 20, 9, 0)),
      _reminder(id: '2', datetime: DateTime(2026, 5, 23, 9, 0)),
    ];

    final sections = buildReminderSections(
      reminders,
      ReminderListFilter.all,
      now: now,
    );

    expect(sections.first.bucket, ReminderDateBucket.overdue);
    expect(sections.first.reminders.single.id, '1');
  });

  test('today filter excludes overdue and completed', () {
    final reminders = [
      _reminder(id: 'past', datetime: DateTime(2026, 5, 20, 9, 0)),
      _reminder(id: 'today', datetime: DateTime(2026, 5, 23, 9, 0)),
      _reminder(
        id: 'done',
        datetime: DateTime(2026, 5, 23, 10, 0),
        status: 'completed',
      ),
    ];

    final sections = buildReminderSections(
      reminders,
      ReminderListFilter.today,
      now: now,
    );

    expect(sections.length, 1);
    expect(sections.single.reminders.map((r) => r.id), ['today']);
  });
}

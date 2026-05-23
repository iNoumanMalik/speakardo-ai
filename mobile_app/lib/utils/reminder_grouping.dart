import '../models/reminder.dart';

enum ReminderListFilter { all, today, tomorrow, upcoming, completed }

enum ReminderDateBucket { overdue, today, tomorrow, upcoming, completed }

class ReminderSection {
  final ReminderDateBucket bucket;
  final List<Reminder> reminders;

  const ReminderSection({
    required this.bucket,
    required this.reminders,
  });

  String get title {
    switch (bucket) {
      case ReminderDateBucket.overdue:
        return 'Overdue';
      case ReminderDateBucket.today:
        return 'Today';
      case ReminderDateBucket.tomorrow:
        return 'Tomorrow';
      case ReminderDateBucket.upcoming:
        return 'Upcoming';
      case ReminderDateBucket.completed:
        return 'Completed';
    }
  }
}

DateTime startOfDay(DateTime dateTime) {
  return DateTime(dateTime.year, dateTime.month, dateTime.day);
}

bool isSameCalendarDay(DateTime a, DateTime b) {
  return a.year == b.year && a.month == b.month && a.day == b.day;
}

ReminderDateBucket bucketFor(Reminder reminder, DateTime now) {
  if (reminder.isCompleted) {
    return ReminderDateBucket.completed;
  }

  final scheduledDay = startOfDay(reminder.datetime);
  final today = startOfDay(now);
  final tomorrow = today.add(const Duration(days: 1));

  if (scheduledDay.isBefore(today)) {
    return ReminderDateBucket.overdue;
  }
  if (isSameCalendarDay(scheduledDay, today)) {
    return ReminderDateBucket.today;
  }
  if (isSameCalendarDay(scheduledDay, tomorrow)) {
    return ReminderDateBucket.tomorrow;
  }
  return ReminderDateBucket.upcoming;
}

bool reminderMatchesFilter(Reminder reminder, ReminderListFilter filter, DateTime now) {
  switch (filter) {
    case ReminderListFilter.all:
      return true;
    case ReminderListFilter.completed:
      return reminder.isCompleted;
    case ReminderListFilter.today:
      return !reminder.isCompleted && bucketFor(reminder, now) == ReminderDateBucket.today;
    case ReminderListFilter.tomorrow:
      return !reminder.isCompleted && bucketFor(reminder, now) == ReminderDateBucket.tomorrow;
    case ReminderListFilter.upcoming:
      return !reminder.isCompleted && bucketFor(reminder, now) == ReminderDateBucket.upcoming;
  }
}

const List<ReminderDateBucket> _sectionOrder = [
  ReminderDateBucket.overdue,
  ReminderDateBucket.today,
  ReminderDateBucket.tomorrow,
  ReminderDateBucket.upcoming,
  ReminderDateBucket.completed,
];

List<ReminderSection> buildReminderSections(
  List<Reminder> reminders,
  ReminderListFilter filter, {
  DateTime? now,
}) {
  final clock = now ?? DateTime.now();
  final sorted = List<Reminder>.from(reminders)
    ..sort((a, b) => a.datetime.compareTo(b.datetime));

  if (filter != ReminderListFilter.all) {
    final filtered = sorted
        .where((r) => reminderMatchesFilter(r, filter, clock))
        .toList();
    if (filtered.isEmpty) {
      return [];
    }

    final bucket = filter == ReminderListFilter.completed
        ? ReminderDateBucket.completed
        : _bucketForFilter(filter);

    return [
      ReminderSection(bucket: bucket, reminders: filtered),
    ];
  }

  final grouped = <ReminderDateBucket, List<Reminder>>{};
  for (final reminder in sorted) {
    final bucket = bucketFor(reminder, clock);
    grouped.putIfAbsent(bucket, () => []).add(reminder);
  }

  return _sectionOrder
      .where((bucket) => grouped[bucket]?.isNotEmpty ?? false)
      .map(
        (bucket) => ReminderSection(
          bucket: bucket,
          reminders: grouped[bucket]!,
        ),
      )
      .toList();
}

ReminderDateBucket _bucketForFilter(ReminderListFilter filter) {
  switch (filter) {
    case ReminderListFilter.today:
      return ReminderDateBucket.today;
    case ReminderListFilter.tomorrow:
      return ReminderDateBucket.tomorrow;
    case ReminderListFilter.upcoming:
      return ReminderDateBucket.upcoming;
    case ReminderListFilter.completed:
      return ReminderDateBucket.completed;
    case ReminderListFilter.all:
      return ReminderDateBucket.today;
  }
}

String emptyMessageForFilter(ReminderListFilter filter) {
  switch (filter) {
    case ReminderListFilter.all:
      return 'No reminders yet.\nTry chat to create one!';
    case ReminderListFilter.today:
      return 'Nothing scheduled for today.';
    case ReminderListFilter.tomorrow:
      return 'Nothing scheduled for tomorrow.';
    case ReminderListFilter.upcoming:
      return 'No upcoming reminders.';
    case ReminderListFilter.completed:
      return 'No completed reminders yet.';
  }
}

bool isReminderOverdue(Reminder reminder, DateTime now) {
  return !reminder.isCompleted && reminder.datetime.isBefore(now);
}

String formatReminderSchedule(Reminder reminder, DateTime now) {
  final time = _formatTime(reminder.datetime);

  if (reminder.isCompleted) {
    return '${_formatDateLabel(reminder.datetime, now)} at $time';
  }

  final bucket = bucketFor(reminder, now);
  switch (bucket) {
    case ReminderDateBucket.today:
      return 'Today at $time';
    case ReminderDateBucket.tomorrow:
      return 'Tomorrow at $time';
    case ReminderDateBucket.overdue:
      return '${_formatDateLabel(reminder.datetime, now)} at $time';
    case ReminderDateBucket.upcoming:
    case ReminderDateBucket.completed:
      return '${_formatDateLabel(reminder.datetime, now)} at $time';
  }
}

String _formatTime(DateTime dateTime) {
  final hour = dateTime.hour % 12 == 0 ? 12 : dateTime.hour % 12;
  final minute = dateTime.minute.toString().padLeft(2, '0');
  final period = dateTime.hour >= 12 ? 'PM' : 'AM';
  return '$hour:$minute $period';
}

String _formatDateLabel(DateTime dateTime, DateTime now) {
  final scheduledDay = startOfDay(dateTime);
  final today = startOfDay(now);
  final yesterday = today.subtract(const Duration(days: 1));

  if (isSameCalendarDay(scheduledDay, yesterday)) {
    return 'Yesterday';
  }
  if (dateTime.year == now.year) {
    const months = [
      'Jan',
      'Feb',
      'Mar',
      'Apr',
      'May',
      'Jun',
      'Jul',
      'Aug',
      'Sep',
      'Oct',
      'Nov',
      'Dec',
    ];
    return '${months[dateTime.month - 1]} ${dateTime.day}';
  }
  return '${dateTime.year}-${dateTime.month.toString().padLeft(2, '0')}-${dateTime.day.toString().padLeft(2, '0')}';
}

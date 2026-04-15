import 'package:intl/intl.dart';

class Reminder {
  final String id;
  final String task;
  final DateTime datetime;
  final String? repeat;
  final String status;

  Reminder({
    required this.id,
    required this.task,
    required this.datetime,
    this.repeat,
    required this.status,
  });

  factory Reminder.fromJson(Map<String, dynamic> json) {
    final utc = DateTime.parse(json['datetime']);
    return Reminder(
      id: json['id'],
      task: json['task'],
      datetime: utc.toLocal(),
      repeat: json['repeat'],
      status: json['status'],
    );
  }

  String get formattedDate => DateFormat('yyyy-MM-dd').format(datetime);
  String get formattedTime => DateFormat('HH:mm').format(datetime);
  bool get isCompleted => status == 'completed';
}

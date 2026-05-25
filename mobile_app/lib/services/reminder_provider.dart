import 'package:flutter/material.dart';
import '../models/reminder.dart';
import 'api_service.dart';

class ReminderProvider with ChangeNotifier {
  final ApiService _apiService = ApiService();
  List<Reminder> _reminders = [];
  bool _isLoading = false;

  List<Reminder> get reminders => _reminders;
  bool get isLoading => _isLoading;
  String? get highlightReminderId => _highlightReminderId;

  String? _highlightReminderId;

  /// Load reminders and scroll/highlight [reminderId] in the list UI.
  Future<void> openReminderInList(String reminderId) async {
    _highlightReminderId = reminderId;
    await fetchReminders();
  }

  void clearHighlight() {
    if (_highlightReminderId == null) return;
    _highlightReminderId = null;
    notifyListeners();
  }

  Future<void> fetchReminders() async {
    _isLoading = true;
    notifyListeners();

    try {
      final List<dynamic> data = await _apiService.getReminders();
      _reminders = data.map((json) => Reminder.fromJson(json)).toList();
      _reminders.sort((a, b) => a.datetime.compareTo(b.datetime));
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> completeReminder(String id) async {
    await _apiService.completeReminder(id);
    final index = _reminders.indexWhere((r) => r.id == id);
    if (index == -1) return;
    final reminder = _reminders[index];
    _reminders[index] = Reminder(
      id: reminder.id,
      task: reminder.task,
      datetime: reminder.datetime,
      repeat: reminder.repeat,
      status: 'completed',
    );
    notifyListeners();
  }

  Future<void> deleteReminder(String id) async {
    await _apiService.deleteReminder(id);
    _reminders.removeWhere((r) => r.id == id);
    notifyListeners();
  }

  void _upsertReminder(Reminder updated) {
    final index = _reminders.indexWhere((r) => r.id == updated.id);
    if (index == -1) {
      _reminders.add(updated);
    } else {
      _reminders[index] = updated;
    }
    _reminders.sort((a, b) => a.datetime.compareTo(b.datetime));
  }

  Future<Reminder> updateReminder(
    String id, {
    required String task,
    required DateTime localDateTime,
    String? repeat,
  }) async {
    final json = await _apiService.patchReminder(id, {
      'task': task,
      'datetime': localDateTime.toUtc().toIso8601String(),
      'repeat': repeat,
    });
    final updated = Reminder.fromJson(json);
    _upsertReminder(updated);
    notifyListeners();
    return updated;
  }

  Future<Reminder> republishReminder(
    String id, {
    String? task,
    DateTime? localDateTime,
    String? repeat,
  }) async {
    final json = await _apiService.republishReminder(
      id,
      task: task,
      datetimeUtcIso: localDateTime?.toUtc().toIso8601String(),
      repeat: repeat,
    );
    final updated = Reminder.fromJson(json);
    _upsertReminder(updated);
    notifyListeners();
    return updated;
  }
}

import 'package:flutter/material.dart';
import '../models/reminder.dart';
import 'api_service.dart';

class ReminderProvider with ChangeNotifier {
  final ApiService _apiService = ApiService();
  List<Reminder> _reminders = [];
  bool _isLoading = false;

  List<Reminder> get reminders => _reminders;
  bool get isLoading => _isLoading;

  Future<void> fetchReminders() async {
    _isLoading = true;
    notifyListeners();

    try {
      final List<dynamic> data = await _apiService.getReminders();
      _reminders = data.map((json) => Reminder.fromJson(json)).toList();
      // Sort by datetime
      _reminders.sort((a, b) => a.datetime.compareTo(b.datetime));
    } catch (e) {
      debugPrint("Error fetching reminders: $e");
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> completeReminder(String id) async {
    try {
      await _apiService.completeReminder(id);
      await fetchReminders();
    } catch (e) {
      debugPrint("Error completing reminder: $e");
    }
  }

  Future<void> deleteReminder(String id) async {
    try {
      await _apiService.deleteReminder(id);
      await fetchReminders();
    } catch (e) {
      debugPrint("Error deleting reminder: $e");
    }
  }
}

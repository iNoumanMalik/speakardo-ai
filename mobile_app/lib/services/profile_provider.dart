import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_timezone/flutter_timezone.dart';

import '../models/user_profile.dart';
import 'profile_service.dart';

class ProfileProvider with ChangeNotifier {
  ProfileProvider() {
    unawaited(fetchProfile());
  }

  final ProfileService _profileService = ProfileService();

  UserProfile? _profile;
  bool _isLoading = false;
  bool _isSaving = false;
  String? _error;

  UserProfile? get profile => _profile;
  bool get isLoading => _isLoading;
  bool get isSaving => _isSaving;
  String? get error => _error;

  String get timezone => _profile?.timezone ?? 'UTC';
  bool get notificationsEnabled => _profile?.notificationsEnabled ?? true;

  Future<void> fetchProfile() async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      _profile = await _profileService.fetchProfile();
    } catch (e) {
      _error = 'Could not load profile';
      debugPrint('Profile load error: $e');
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<bool> setNotificationsEnabled(bool enabled) async {
    return _savePreferences(notificationsEnabled: enabled);
  }

  Future<bool> setTimezone(String timezone) async {
    return _savePreferences(timezone: timezone);
  }

  Future<bool> useDeviceTimezone() async {
    try {
      final deviceTimezone = await FlutterTimezone.getLocalTimezone();
      return setTimezone(deviceTimezone);
    } catch (e) {
      debugPrint('Device timezone error: $e');
      return false;
    }
  }

  Future<bool> _savePreferences({
    String? timezone,
    bool? notificationsEnabled,
  }) async {
    _isSaving = true;
    _error = null;
    notifyListeners();

    try {
      _profile = await _profileService.updatePreferences(
        timezone: timezone,
        notificationsEnabled: notificationsEnabled,
      );
      return true;
    } catch (e) {
      _error = 'Could not save preferences';
      debugPrint('Profile save error: $e');
      return false;
    } finally {
      _isSaving = false;
      notifyListeners();
    }
  }
}

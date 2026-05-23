import 'package:flutter_test/flutter_test.dart';
import 'package:mobile_app/utils/timezone_clock.dart';
import 'package:timezone/data/latest_all.dart';
import 'package:timezone/timezone.dart' as tz;

void main() {
  setUpAll(() {
    initializeTimeZones();
  });

  test('clockNowInTimezone returns a valid DateTime for UTC', () {
    final clock = clockNowInTimezone('UTC');
    expect(clock.year, greaterThan(2020));
  });

  test('clockNowInTimezone falls back for invalid timezone', () {
    final before = DateTime.now();
    final clock = clockNowInTimezone('Not/A_Real_Zone');
    final after = DateTime.now();
    expect(clock.isAfter(before.subtract(const Duration(seconds: 2))), isTrue);
    expect(clock.isBefore(after.add(const Duration(seconds: 2))), isTrue);
  });
}

import 'package:timezone/timezone.dart' as tz;

/// Returns "now" as a plain [DateTime] in the given IANA timezone.
DateTime clockNowInTimezone(String timezoneName) {
  try {
    final location = tz.getLocation(timezoneName);
    final zoned = tz.TZDateTime.now(location);
    return DateTime(
      zoned.year,
      zoned.month,
      zoned.day,
      zoned.hour,
      zoned.minute,
      zoned.second,
    );
  } catch (_) {
    return DateTime.now();
  }
}

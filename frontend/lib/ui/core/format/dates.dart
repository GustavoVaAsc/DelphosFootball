/// Date formatting: "27 may 2026", seasons as "2025/26", and whole ages.
///
/// The three helpers stay together because they are the app's only
/// calendar arithmetic; none of them justifies a file of its own.
library;

import 'numbers.dart';

const List<String> _monthsShort = [
  'ene', 'feb', 'mar', 'abr', 'may', 'jun', //
  'jul', 'ago', 'sep', 'oct', 'nov', 'dic',
];

/// "27 may 2026": day, short Spanish month in lower case, year. A UTC
/// date-time (a report's `created_at`) prints in the reader's local time; a
/// date-only value is already local and prints unchanged.
String formatDate(DateTime? date) {
  if (date == null) return notAvailable;
  final local = date.toLocal();
  return '${local.day} ${_monthsShort[local.month - 1]} ${local.year}';
}

/// "2025/26": the season that starts in [season].
String formatSeason(int season) {
  final end = ((season + 1) % 100).toString().padLeft(2, '0');
  return '$season/$end';
}

/// Whole years between [birthDate] and [reference], never rounded up.
int? ageOn(DateTime? birthDate, DateTime? reference) {
  if (birthDate == null || reference == null) return null;
  final beforeBirthday =
      reference.month < birthDate.month ||
      (reference.month == birthDate.month && reference.day < birthDate.day);
  return reference.year - birthDate.year - (beforeBirthday ? 1 : 0);
}

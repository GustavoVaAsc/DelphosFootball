/// Parsing for the numeric ids and counters that arrive in a URL: the
/// explorer's `arquetipo`, `pagina` and `jugador`, and the comparator's
/// `:playerId`.
library;

final RegExp _digits = RegExp(r'^\d{1,10}$');

/// The largest id the app accepts: the backend's 32-bit integer maximum.
const int maxRouteId = 2147483647;

/// [value] as an integer when it is one to ten ASCII digits and at most
/// [maxRouteId]; otherwise `null`. Signs, spaces, hex and exponents are
/// rejected, so a crafted link cannot reach the API with an odd id.
int? parseRouteId(String? value) {
  if (value == null || !_digits.hasMatch(value)) return null;
  final number = int.parse(value);
  return number <= maxRouteId ? number : null;
}

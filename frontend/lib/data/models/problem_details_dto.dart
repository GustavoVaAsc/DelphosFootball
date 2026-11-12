/// The RFC 9457 problem document the backend sends with every error
/// (`backend/src/delphos_backend/schemas/errors.py`).
library;

/// A parsed `application/problem+json` body.
class ProblemDetailsDto {
  const ProblemDetailsDto({
    required this.title,
    required this.status,
    this.detail,
  });

  /// Parses a problem body, or returns `null` when [json] is not one.
  static ProblemDetailsDto? tryParse(Object? json) => switch (json) {
    {'title': String title, 'status': int status} => ProblemDetailsDto(
      title: title,
      status: status,
      detail: switch (json['detail']) {
        final String detail => detail,
        _ => null,
      },
    ),
    _ => null,
  };

  final String title;
  final int status;
  final String? detail;
}

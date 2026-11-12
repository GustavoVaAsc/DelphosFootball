/// One dossier section's load: its status and, when ready, its value.
library;

import 'section_status.dart';

/// An immutable snapshot of a section's request.
class SectionLoad<T> {
  const SectionLoad.loading() : status = SectionStatus.loading, value = null;
  const SectionLoad.ready(T this.value) : status = SectionStatus.ready;
  const SectionLoad.absent() : status = SectionStatus.absent, value = null;
  const SectionLoad.error() : status = SectionStatus.error, value = null;

  final SectionStatus status;

  /// The data, only when [status] is ready.
  final T? value;
}

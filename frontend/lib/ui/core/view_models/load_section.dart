/// Turns one request into a section state: ready with its value, absent on
/// a 404 when the caller allows it (the pipeline has nothing for this
/// player), or error on any other failure. Shared by the dossier and the
/// comparator, which both load several independent sections per player.
library;

import '../../../data/services/api_exception.dart';
import 'section_load.dart';

/// Runs [fetch] and maps its outcome to a [SectionLoad].
Future<SectionLoad<T>> loadSection<T>(
  Future<T> Function() fetch, {
  bool absentOnNotFound = true,
}) async {
  try {
    return SectionLoad.ready(await fetch());
  } on ApiException catch (error) {
    return absentOnNotFound && error.isNotFound
        ? SectionLoad<T>.absent()
        : SectionLoad<T>.error();
  } on Exception {
    return SectionLoad<T>.error();
  }
}

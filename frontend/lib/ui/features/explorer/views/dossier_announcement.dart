/// The dossier's spoken status (DESIGN.md §4): one polite announcement when
/// it opens ("Ficha de X abierta") or closes ("Ficha cerrada"), instead of
/// re-reading the panel. Never on page load: only a change announces.
library;

import 'package:flutter/semantics.dart';
import 'package:flutter/widgets.dart';

/// The message for a dossier change, or `null` when there is nothing to
/// say (a player opened whose name is not known yet).
String? dossierAnnouncement({required int? opened, String? name}) {
  if (opened == null) return 'Ficha cerrada';
  return name == null ? null : 'Ficha de $name abierta';
}

/// Sends [message] politely to the screen reader of [context]'s view.
void announceDossier(BuildContext context, String? message) {
  if (message == null) return;
  SemanticsService.sendAnnouncement(
    View.of(context),
    message,
    TextDirection.ltr,
  );
}

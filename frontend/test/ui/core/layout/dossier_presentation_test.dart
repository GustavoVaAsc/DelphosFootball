// Tests for the one responsive breakpoint (ADR-027): below 1100 px the
// dossier opens as its own page instead of a side panel.
import 'package:delphos_frontend/ui/core/layout/dossier_presentation.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('opens as a side panel from 1100 px up', () {
    expect(DossierPresentation.forWidth(1920), DossierPresentation.sidePanel);
    expect(DossierPresentation.forWidth(1280), DossierPresentation.sidePanel);
    expect(DossierPresentation.forWidth(1100), DossierPresentation.sidePanel);
  });

  test('opens as a full-width page below 1100 px', () {
    expect(DossierPresentation.forWidth(1099.9), DossierPresentation.fullPage);
    expect(DossierPresentation.forWidth(800), DossierPresentation.fullPage);
  });
}

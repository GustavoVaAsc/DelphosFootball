// Pumps the whole app at a location, at the 1440 x 900 design size, with
// the fake explorer backend.
import 'dart:io';

import 'package:delphos_frontend/app.dart';
import 'package:delphos_frontend/routing/app_router.dart';
import 'package:delphos_frontend/ui/core/widgets/focus_visibility.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter/services.dart';

import 'explorer_harness.dart';

Future<GoRouter> pumpAppAt(
  WidgetTester tester,
  String location, {
  FakePlayersBackend? backend,

  /// False leaves the app mid-load, for tests of what animates while it
  /// settles; the caller pumps.
  bool settle = true,
}) async {
  await loadArchivo();
  // Ring visibility is static state: start each app from "no input yet" and
  // leave nothing behind for the next test, even if this one throws.
  FocusVisibility.reset();
  addTearDown(FocusVisibility.reset);
  tester.view.physicalSize = const Size(1440, 900);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  final router = buildAppRouter(initialLocation: location);
  addTearDown(router.dispose);
  final api = (backend ?? FakePlayersBackend()).api;
  addTearDown(api.close);
  await tester.pumpWidget(DelphosApp(apiClient: api, router: router));
  if (settle) await tester.pumpAndSettle();
  return router;
}

String currentPath(GoRouter router) =>
    router.routerDelegate.currentConfiguration.uri.path;

bool _archivoLoaded = false;

/// Registers the bundled fonts (`Archivo`, `LeagueSpartan`, `SourceSans3`),
/// so widget tests lay text out with the app's real metrics instead of the
/// wide test font.
Future<void> loadArchivo() async {
  if (_archivoLoaded) return;
  const fonts = {
    'Archivo': 'assets/fonts/archivo/Archivo-Variable.ttf',
    'LeagueSpartan': 'assets/fonts/league_spartan/LeagueSpartan-Variable.ttf',
    'SourceSans3': 'assets/fonts/source_sans_3/SourceSans3-Variable.ttf',
  };
  for (final entry in fonts.entries) {
    final bytes = File(entry.value).readAsBytesSync();
    final loader = FontLoader(entry.key)
      ..addFont(Future.value(ByteData.view(bytes.buffer)));
    await loader.load();
  }
  _archivoLoaded = true;
}

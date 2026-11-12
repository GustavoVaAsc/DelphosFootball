// Pumps the whole app at a location, at the 1440 x 900 design size, with
// the fake explorer backend.
import 'dart:io';

import 'package:delphos_frontend/app.dart';
import 'package:delphos_frontend/routing/app_router.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter/services.dart';

import 'explorer_harness.dart';

Future<GoRouter> pumpAppAt(
  WidgetTester tester,
  String location, {
  FakePlayersBackend? backend,
}) async {
  await loadArchivo();
  tester.view.physicalSize = const Size(1440, 900);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  final router = buildAppRouter(initialLocation: location);
  addTearDown(router.dispose);
  final api = (backend ?? FakePlayersBackend()).api;
  addTearDown(api.close);
  await tester.pumpWidget(DelphosApp(apiClient: api, router: router));
  await tester.pumpAndSettle();
  return router;
}

String currentPath(GoRouter router) =>
    router.routerDelegate.currentConfiguration.uri.path;

bool _archivoLoaded = false;

/// Registers the bundled Archivo font, so widget tests lay text out with the
/// app's real metrics instead of the wide test font.
Future<void> loadArchivo() async {
  if (_archivoLoaded) return;
  final bytes = File('assets/fonts/archivo/Archivo-Variable.ttf')
      .readAsBytesSync();
  final loader = FontLoader('Archivo')
    ..addFont(Future.value(ByteData.view(bytes.buffer)));
  await loader.load();
  _archivoLoaded = true;
}

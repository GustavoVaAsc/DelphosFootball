/// The route table (ADR-024): the URL is the state, so a reload or a shared
/// link restores the same view, filters and open dossier.
///
/// Each module page builds the shell itself instead of sitting in a
/// `ShellRoute`: a `ShellRoute` puts the page in a nested navigator whose
/// route focus scope traps Tab, so keyboard focus could never leave the page
/// for the sidebar. The shell holds no state, so rebuilding it per page
/// costs nothing visible.
library;

import 'package:flutter/widgets.dart';
import 'package:go_router/go_router.dart';

import '../ui/core/shell/app_shell.dart';
import '../ui/core/shell/not_found_screen.dart';
import '../ui/core/widgets/enter_motion.dart';
import '../ui/features/archetypes/views/archetypes_screen.dart';
import '../ui/features/chat/views/chat_screen.dart';
import '../ui/features/comparator/views/comparator_screen.dart';
import '../ui/features/explorer/views/explorer_screen.dart';
import 'explorer_query.dart';
import 'route_params.dart';
import 'routes.dart';

/// Builds the router. Pages switch without a route transition; the view
/// change of DESIGN.md §5 is `EnterMotion` around the screen in `_modulePage`.
GoRouter buildAppRouter({String initialLocation = Routes.explorer}) => GoRouter(
  initialLocation: initialLocation,
  errorBuilder: (_, _) => const NotFoundScreen(),
  routes: [
    GoRoute(path: Routes.root, redirect: (_, _) => Routes.explorer),
    GoRoute(
      path: Routes.explorer,
      pageBuilder: (_, state) => _modulePage(
        state,
        ExplorerScreen(
          query: ExplorerQuery.fromQueryParameters(state.uri.queryParameters),
        ),
      ),
    ),
    GoRoute(
      path: Routes.comparator,
      pageBuilder: (_, state) => _modulePage(state, const ComparatorScreen()),
      routes: [
        GoRoute(
          path: ':playerId',
          redirect: (_, state) =>
              _playerId(state) == null ? Routes.comparator : null,
          pageBuilder: (_, state) =>
              _modulePage(state, ComparatorScreen(playerId: _playerId(state))),
        ),
      ],
    ),
    GoRoute(
      path: Routes.archetypes,
      pageBuilder: (_, state) => _modulePage(state, const ArchetypesScreen()),
    ),
    GoRoute(
      path: Routes.chat,
      pageBuilder: (_, state) => _modulePage(state, const ChatScreen()),
    ),
  ],
);

/// A module page: [screen] inside the shell. The route itself has no
/// transition, so the sidebar and top bar stay put; only the screen fades in
/// (200 ms, opacity and 4 px up) to mark the change of view (DESIGN.md §5).
/// The page key does not include the query, so filtering inside the explorer
/// keeps the screen and plays nothing.
Page<void> _modulePage(GoRouterState state, Widget screen) => NoTransitionPage(
  key: state.pageKey,
  child: AppShell(
    location: state.uri.path,
    child: EnterMotion(offset: const Offset(0, 4), child: screen),
  ),
);

/// A positive player id from the path (`parseRouteId`), or `null`.
int? _playerId(GoRouterState state) =>
    switch (parseRouteId(state.pathParameters['playerId'])) {
      final id? when id >= 1 => id,
      _ => null,
    };

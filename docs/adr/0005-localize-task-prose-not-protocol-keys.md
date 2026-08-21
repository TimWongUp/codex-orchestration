# Localize task prose, not protocol keys

Task packages keep canonical field names and fixed control literals while their descriptive prose and requested return language follow an explicit user request, then a saved local `en` or `zh-CN` preference, then the current user's language. We chose this boundary so users can work consistently in their preferred language without forking the portable lease, Hook, or task-package contracts.

**Status:** accepted

**Consequences:** Initial setup offers English or Simplified Chinese and may persist the choice outside the repository. Agent profiles remain language-neutral, and direct user instructions always override the saved preference.

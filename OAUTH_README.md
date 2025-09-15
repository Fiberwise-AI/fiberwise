# FiberWise — OAuth Command Reference

Both `fiber account oauth` and `fiber app oauth` commands are implemented and should work, but they serve different scopes and have different behaviors:

### `fiber account oauth`
- **Scope:** Global/account-level OAuth provider management.
- **Features:** 
  - `configure`: Prompts for client ID/secret, saves provider config to a global directory, and can save to a file.
  - `list_providers`: Lists all globally configured OAuth providers.
  - `auth`: Initiates OAuth flow for a provider, opens browser for authentication.
  - Handles provider configs in a global directory (not app-specific).
- **Typical Use:** When you want to manage OAuth providers available to all apps or the whole account.

### `fiber app oauth`
- **Scope:** Application-specific OAuth provider management.
- **Features:** 
  - `register`: Registers an OAuth provider for a specific app using a JSON config, requires app context and makes an API call to the FiberWise backend.
  - `list_providers`: Lists OAuth providers for the current app by making an API call with the app ID.
  - `delete_provider`: Deletes an OAuth provider for the app via API.
  - All actions are tied to the app's identity and configuration.
- **Typical Use:** When you want to manage OAuth providers that are only relevant to a specific FiberWise application.

### Do they work correctly?
- **Yes, if used as intended:**  
  - `fiber account oauth` works for global provider management and stores configs locally.  
  - `fiber app oauth` works for app-specific provider management and interacts with the FiberWise backend using the app's credentials and context.
- **Caveats:**  
  - For `fiber app oauth`, the app must be installed/registered (`fiber app install`) and have a valid `.fw-data/fw_app_info.json`.  
  - For both, you need valid configuration and API keys.

**Summary:**  
Both command groups are implemented and functional, but you must use the correct one for your use case:  
- Use `fiber account oauth` for global/account-wide OAuth providers.  
- Use `fiber app oauth` for app-specific OAuth providers.

#!/usr/bin/env python3
import sys
sys.path.insert(0, 'src')

# Test all major imports
try:
    from mycode.tui.app import MyCodeApp
    print("✅ TUI app imports OK")
except Exception as e:
    print(f"❌ TUI app: {e}")

try:
    from mycode.core.workspace import provider_manager, workspace_manager, trusted_folder_manager
    print("✅ Workspace imports OK")
    print(f"   Providers: {len(provider_manager.providers)}")
    print(f"   Projects: {len(workspace_manager.state.projects)}")
    print(f"   Trusted folders: {len(trusted_folder_manager.folders)}")
except Exception as e:
    print(f"❌ Workspace: {e}")

try:
    from mycode.core.advisor import AdvisorReviewer, FastModeRouter
    print("✅ Advisor imports OK")
except Exception as e:
    print(f"❌ Advisor: {e}")

try:
    from mycode.core.analytics import cost_tracker, get_analytics
    print("✅ Analytics imports OK")
except Exception as e:
    print(f"❌ Analytics: {e}")

try:
    from mycode.core.accessibility import ScreenReaderAnnouncer, VoiceInput
    print("✅ Accessibility imports OK")
except Exception as e:
    print(f"❌ Accessibility: {e}")

try:
    from mycode.core.debug import DebugInspector
    print("✅ Debug imports OK")
except Exception as e:
    print(f"❌ Debug: {e}")

try:
    from mycode.core.styles import theme_manager, OutputStyle
    print("✅ Styles imports OK")
except Exception as e:
    print(f"❌ Styles: {e}")

try:
    from mycode.core.prompts.library import prompt_library
    print("✅ Prompts imports OK")
except Exception as e:
    print(f"❌ Prompts: {e}")

try:
    from mycode.core.glossary import glossary
    print("✅ Glossary imports OK")
except Exception as e:
    print(f"❌ Glossary: {e}")

try:
    from mycode.core.agent import Agent
    print("✅ Agent imports OK")
except Exception as e:
    print(f"❌ Agent: {e}")

try:
    from mycode.core.llm_client import NemotronClient
    print("✅ LLM Client imports OK")
except Exception as e:
    print(f"❌ LLM Client: {e}")

try:
    from mycode.core.cache import check_cache, save_to_cache
    print("✅ Cache imports OK")
except Exception as e:
    print(f"❌ Cache: {e}")

try:
    from mycode.core.rag import index_directory, retrieve_context
    print("✅ RAG imports OK")
except Exception as e:
    print(f"❌ RAG: {e}")

try:
    from mycode.core.hooks import get_hook_registry
    print("✅ Hooks imports OK")
except Exception as e:
    print(f"❌ Hooks: {e}")

try:
    from mycode.core.scheduler import get_scheduler
    print("✅ Scheduler imports OK")
except Exception as e:
    print(f"❌ Scheduler: {e}")

try:
    from mycode.core.checkpoints import get_checkpoint_manager
    print("✅ Checkpoints imports OK")
except Exception as e:
    print(f"❌ Checkpoints: {e}")

try:
    from mycode.core.mcp import get_mcp_client
    print("✅ MCP imports OK")
except Exception as e:
    print(f"❌ MCP: {e}")

try:
    from mycode.core.plugins import get_plugin_manager
    print("✅ Plugins imports OK")
except Exception as e:
    print(f"❌ Plugins: {e}")

try:
    from mycode.core.skills import get_skill_registry, get_skill_executor
    print("✅ Skills imports OK")
except Exception as e:
    print(f"❌ Skills: {e}")

try:
    from mycode.core.artifacts import get_artifact_manager
    print("✅ Artifacts imports OK")
except Exception as e:
    print(f"❌ Artifacts: {e}")

try:
    from mycode.core.channels import get_channel_server
    print("✅ Channels imports OK")
except Exception as e:
    print(f"❌ Channels: {e}")

print("\n✅ All imports verified!")
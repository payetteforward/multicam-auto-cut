"""
Editing profiles for different recording scenarios.
"""

from dataclasses import dataclass
from typing import Dict

@dataclass
class EditingProfile:
    """Configuration for different editing styles based on recording type."""

    name: str
    description: str
    prompt_template: str
    preserve_navigation: bool = True
    preserve_pauses: bool = True
    aggressive_filler_removal: bool = False

    def get_prompt(self, transcript: str) -> str:
        """Generate the editing prompt for this profile."""
        return self.prompt_template.format(transcript=transcript)


# Pre-defined editing profiles
PROFILES: Dict[str, EditingProfile] = {
    "scripted": EditingProfile(
        name="Scripted Recording",
        description="For recordings with a prepared script. Minimal editing, preserve performance.",
        prompt_template="""You are preparing a first-pass edit of a scripted video. The speaker has a prepared script, so most content is intentional.

REMOVE ONLY:
1. Complete false starts or restarts
2. Technical issues or interruptions
3. Obvious mistakes or corrections

KEEP EVERYTHING ELSE:
- All scripted content
- Natural pauses and pacing
- Navigation time between UI elements
- Slight variations (may be intentional)
- Natural filler words that maintain rhythm

This is a polished recording that needs minimal editing.

Original transcript:
{transcript}

Return ONLY the cleaned transcript text.""",
        preserve_navigation=True,
        preserve_pauses=True,
        aggressive_filler_removal=False
    ),

    "tutorial": EditingProfile(
        name="Tutorial/Demo",
        description="For tutorial recordings with natural explanations. Balanced editing.",
        prompt_template="""You are preparing a first-pass edit of a tutorial/demo video. Create a smooth, comprehensive script.

REMOVE ONLY:
1. Complete false starts where the speaker restarts
2. Technical issues or off-topic asides
3. Excessive filler words that disrupt flow
4. Exact duplicate explanations
5. Abandoned thoughts

ALWAYS KEEP:
1. Navigation time while moving between UI elements
2. Natural pauses for viewer comprehension
3. Variations in explanation
4. Complete teaching narrative
5. Intentional emphasis

Preserve natural pacing and smooth transitions.

Original transcript:
{transcript}

Return ONLY the cleaned transcript text.""",
        preserve_navigation=True,
        preserve_pauses=True,
        aggressive_filler_removal=False
    ),

    "rough": EditingProfile(
        name="Rough Recording",
        description="For unscripted, impromptu recordings. More aggressive editing.",
        prompt_template="""You are editing a rough, unscripted recording. Remove redundancy while keeping the core message.

REMOVE:
1. All false starts and restarts
2. Excessive filler words (um, uh, like, you know)
3. Repeated explanations (keep the best one)
4. Rambling or circular thoughts
5. Off-topic tangents

KEEP:
1. Core information and key points
2. The clearest explanation of each concept
3. Navigation pauses (for UI recordings)
4. Natural transitions between topics

Focus on clarity and conciseness.

Original transcript:
{transcript}

Return ONLY the cleaned transcript text.""",
        preserve_navigation=True,
        preserve_pauses=False,
        aggressive_filler_removal=True
    ),

    "podcast": EditingProfile(
        name="Podcast/Interview",
        description="For conversational recordings. Preserve natural speech patterns.",
        prompt_template="""You are editing a conversational recording. Keep the natural flow while removing disruptions.

REMOVE ONLY:
1. Technical issues or interruptions
2. Completely broken thoughts
3. Excessive verbal tics that distract

KEEP:
1. Natural conversational flow
2. Personality and speaking style
3. Thoughtful pauses
4. Natural filler words that maintain rhythm
5. All substantive content

Preserve the authentic conversation.

Original transcript:
{transcript}

Return ONLY the cleaned transcript text.""",
        preserve_navigation=False,
        preserve_pauses=True,
        aggressive_filler_removal=False
    ),

    "aggressive": EditingProfile(
        name="Aggressive Edit",
        description="Maximum cutting for very rough recordings. Create tight, concise output.",
        prompt_template="""You are aggressively editing a very rough recording. Create a tight, concise version.

AGGRESSIVELY REMOVE:
1. ALL filler words and verbal tics
2. ALL false starts and restarts
3. ANY repetition or redundancy
4. Thinking pauses and hesitations
5. Verbose explanations (keep only the most concise)

KEEP ONLY:
1. Essential information
2. The most concise explanation of each point
3. Clear, complete thoughts
4. Navigation markers (if UI recording)

Aim for maximum clarity and brevity.

Original transcript:
{transcript}

Return ONLY the cleaned transcript text.""",
        preserve_navigation=True,
        preserve_pauses=False,
        aggressive_filler_removal=True
    )
}

def get_profile(name: str) -> EditingProfile:
    """Get an editing profile by name."""
    profile = PROFILES.get(name.lower())
    if not profile:
        # Default to tutorial profile
        return PROFILES["tutorial"]
    return profile

def list_profiles() -> Dict[str, str]:
    """List available profiles with descriptions."""
    return {name: profile.description for name, profile in PROFILES.items()}
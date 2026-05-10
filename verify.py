#!/usr/bin/env python3
"""
Quick verification that the refactored pipeline still works.
Run this BEFORE pushing to GitHub to ensure nothing is broken.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_imports():
    """Verify all modules can be imported."""
    print("Testing imports...")
    try:
        from utils.config import GROQ_MODEL, ASSEMBLYAI_BASE_URL, SAMPLE_RATE
        from utils.logger import get_logger
        from audio.vad import load_vad_model, get_speech_segments, keep_only_speech
        from audio.filters import bandpass_filter, remove_impulse_noise, suppress_mouth_noise
        from transcription.formatter import format_transcript, utterances_to_text
        from transcription.transcriber import transcribe_audio
        from intelligence.prompts import EXTRACTION_PROMPT
        from intelligence.extractor import extract_intelligence
        from output.recap import render_recap
        print("✅ All imports successful")
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

def test_formatter():
    """Test transcript formatting without API calls."""
    print("\nTesting formatter...")
    try:
        from transcription.formatter import format_transcript, utterances_to_text
        
        fake_transcript = {
            'utterances': [
                {'start': 5000, 'speaker': 'A', 'text': 'Test utterance one.'},
                {'start': 12000, 'speaker': 'B', 'text': 'Test utterance two.'},
            ]
        }
        
        formatted = format_transcript(fake_transcript)
        assert '[00:05] Speaker A: Test utterance one.' in formatted
        assert '[00:12] Speaker B: Test utterance two.' in formatted
        
        text = utterances_to_text(fake_transcript)
        assert 'Test utterance one.' in text
        
        print("✅ Formatter works correctly")
        return True
    except Exception as e:
        print(f"❌ Formatter test failed: {e}")
        return False

def test_recap():
    """Test recap generation."""
    print("\nTesting recap generation...")
    try:
        from output.recap import render_recap
        
        fake_intelligence = {
            'action_items': [
                {
                    'action': 'Test action',
                    'owner': 'Speaker A',
                    'deadline': 'Friday',
                    'source_quote': 'I will do this by Friday'
                }
            ],
            'decisions': [
                {
                    'decision': 'Test decision',
                    'decided_by': ['A', 'B'],
                    'source_quote': 'We agreed on this'
                }
            ],
            'follow_ups': [],
            'open_questions': []
        }
        
        recap = render_recap(fake_intelligence, 'Test Meeting')
        assert '# Meeting Recap: Test Meeting' in recap
        assert 'Test action' in recap
        assert 'Test decision' in recap
        
        print("✅ Recap generation works correctly")
        return True
    except Exception as e:
        print(f"❌ Recap test failed: {e}")
        return False

def test_config():
    """Test config values are loaded."""
    print("\nTesting config...")
    try:
        from utils.config import GROQ_MODEL, SAMPLE_RATE, VAD_THRESHOLD
        
        assert GROQ_MODEL == "llama-3.3-70b-versatile"
        assert SAMPLE_RATE == 16000
        assert VAD_THRESHOLD == 0.4
        
        print("✅ Config loaded correctly")
        return True
    except Exception as e:
        print(f"❌ Config test failed: {e}")
        return False

def main():
    print("=" * 60)
    print("AI Meeting Intelligence - Pre-Push Verification")
    print("=" * 60)
    
    tests = [
        test_imports,
        test_config,
        test_formatter,
        test_recap,
    ]
    
    results = [test() for test in tests]
    
    print("\n" + "=" * 60)
    if all(results):
        print("✅ ALL TESTS PASSED - Safe to push to GitHub!")
    else:
        print("❌ SOME TESTS FAILED - Fix issues before pushing")
        sys.exit(1)
    print("=" * 60)

if __name__ == "__main__":
    main()

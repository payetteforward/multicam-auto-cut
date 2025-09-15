# New Export Features - Multicam Auto-Cut

## Overview
The multicam auto-cut system now exports to a **new timeline** with all cuts pre-applied, preserving your original timeline completely intact.

## Key Features

### 1. New Timeline Creation
- Creates a completely new sequence/timeline in your project
- Original timeline remains untouched for reference
- New timeline has a unique timestamped name (e.g., `Original_Sequence_AutoCut_20250914_143022`)

### 2. Pre-Made Cuts
- All cuts are already applied in the new timeline
- No blade tool or manual cutting required
- Each segment is a separate multicam clip positioned sequentially
- Maintains frame-accurate timing with proper source references

### 3. Smart Naming Convention
- Output files are automatically named with timestamps
- Format: `{original_name}_AutoCut_{timestamp}.fcpxml`
- Example: `interview_AutoCut_20250914_143022.fcpxml`
- Easy to identify and organize multiple versions

### 4. Seamless Workflow
1. Export your multicam clip from Final Cut Pro as FCPXML
2. Run the auto-cut process
3. Import the generated FCPXML back into Final Cut Pro
4. A new timeline appears with all cuts already made
5. Review and fine-tune as needed

## Technical Details

### What Gets Created
- **New Sequence**: A duplicate of your original sequence structure
- **Cut Segments**: Individual multicam clips for each "keep" section
- **Sequential Layout**: Segments are placed back-to-back with no gaps
- **Proper References**: Each segment references the correct source timecode

### Frame Rate Support
- Maintains original frame rate settings
- Supports 29.97 DF, 24p, 25p, and mixed frame rates
- Frame-accurate cutting preserved

### Metadata
- Generates accompanying JSON file with cut statistics
- Tracks time saved, segments removed, and processing details
- Useful for reviewing what changes were made

## Usage Example

```bash
# Basic usage - auto-generates timestamped output name
python workflow.py your_multicam.fcpxml

# Custom output name
python workflow.py your_multicam.fcpxml -o custom_output.fcpxml

# With aggressive cleaning
python workflow.py your_multicam.fcpxml -c aggressive
```

## Benefits

1. **Non-Destructive**: Original timeline preserved
2. **Time-Saving**: All cuts pre-applied, ready for review
3. **Organized**: Clear naming with timestamps
4. **Flexible**: Easy to compare versions or revert
5. **Professional**: Clean, sequential edit ready for finishing

## Import Back to Final Cut Pro

When you import the generated FCPXML:
1. Your project will show both timelines
2. The new timeline will have "_AutoCut_" in its name
3. All cuts are visible as separate clips in the timeline
4. You can immediately start reviewing and fine-tuning

## Notes

- The system removes silence and filler words based on transcription
- Each cut segment maintains its multicam properties
- You can still switch angles within each segment
- Color correction and effects can be applied to individual segments
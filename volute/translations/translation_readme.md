# VOLUTE Translation System

## Overview

The VOLUTE application uses an external translation system based on TSV (Tab-Separated Values) files with automatic language detection. The system dynamically populates the Language menu based on available translation files, making it extremely easy to add new languages without code modifications.

## Key Features

- **Zero-Configuration Language Addition**: Simply add a TSV file and the language appears in the menu
- **Dynamic Language Detection**: Menu populated automatically from available files  
- **Unicode Support**: Full support for non-Latin scripts (Chinese, Arabic, etc.) with hybrid display approach
- **Robust Fallback**: Automatic fallback to English for missing translations
- **Embedded English Fallback**: Works even if no TSV files are present
- **Translation Validation**: Built-in consistency checking and error reporting
- **Cross-Platform Compatibility**: Reliable Unicode display on Windows, macOS, and Linux

## File Structure

```
tools/volute/
├── localization.py          # Translation manager
└── translations/            # Translation files directory
    ├── en.tsv              # English translations (default)
    ├── fr.tsv              # French translations
    └── [language].tsv      # Additional languages
```

## TSV File Format

Each translation file uses the following tab-separated format:

```
key	translation	context
window_title	VOLUTE	Application window title
select_folder	Select image folder	Button text
```

### Columns:
- **key**: Unique identifier for the text (used in code)
- **translation**: The translated text in the target language  
- **context**: Description to help translators understand usage

### Special Requirements:
- **First non-comment line** must be: `language_name\t[Display Name]\tDisplay name for this language in the menu`
- **UTF-8 encoding** required for all files
- **Tab separation** (not spaces) between columns

## Adding a New Language

### Step 1: Use the Translation Template
1. **Copy the template file**: Copy `translations/template.tsv` to `translations/[language_code].tsv`
   - Example: `translations/de.tsv` for German
2. **Edit the first line**: Change `[Your Language Name]` to your language's display name
   ```
   language_name	Deutsch	Display name for this language in the menu
   ```
3. **Translate the entries**: Translate only the `translation` column (middle column)
4. **Keep structure intact**: Don't modify the `key` or `context` columns
5. **Save as UTF-8**: Ensure the file is saved with UTF-8 encoding

### Step 2: Test Translation
- The language will appear automatically in the menu upon application restart
- No code changes needed!
- Use validation tools to check completeness:

```python
localization_manager = LocalizationManager()
is_valid, result = localization_manager.validate_translation_file("translations/de.tsv")
if not is_valid:
    print("Translation issues found:", result)
```

### Step 3: Verification
- Start application and check Language menu
- Switch to your language and test key UI elements
- Check console for any missing translation warnings

### Translation Template Usage
The `template.tsv` file contains:
- All translation keys with English text
- Detailed context information for each entry
- Proper formatting example
- Complete coverage of all UI elements

**Advantages of using the template:**
- No need to know other languages besides English and target language
- Guarantees completeness (all keys included)
- Consistent formatting
- Up-to-date with latest application version

## Translation Guidelines

### For Translators:

1. **Keep placeholders**: Messages with `{0}`, `{1}` etc. are placeholders for dynamic content
   ```
   prediction_successful	Prediction successful for {0} object(s) on image {1}.
   ```

2. **Preserve formatting**: Keep colons, periods, and other punctuation as appropriate for your language

3. **Use context**: The context column explains where and how the text is used

4. **Test in application**: If possible, test your translations in the running application

### Technical Considerations:

1. **File encoding**: Always save TSV files as UTF-8
2. **Tab separation**: Use actual tab characters, not spaces
3. **No quotes**: Don't wrap translations in quotes unless they're part of the text
4. **Comments**: Lines starting with `#` in the key column are ignored

## Language Codes

Use standard language codes:
- `en` - English (embedded, no TSV file needed)
- `fr` - French  
- `es` - Spanish
- `de` - German
- `it` - Italian
- `pt` - Portuguese
- `ja` - Japanese
- `zh` - Chinese (Simplified)
- `cn` - Chinese (Mandarin)
- `ar` - Arabic
- `ru` - Russian
- etc.

## Common Translation Categories

### UI Elements
- Button labels
- Menu items
- Panel titles
- Checkbox labels

### Messages
- Success messages
- Error messages
- Warning dialogs
- Confirmation prompts

### Technical Terms
- "Object" (segmentation object)
- "Mask" (segmentation mask)
- "Centroid" (center point)
- "Propagation" (mask propagation through video)

## Validation and Quality Assurance

The system includes automatic validation:

### Key Consistency
- All languages must have the same keys
- Missing keys are reported
- Extra keys are flagged

### Placeholder Validation
- Ensures placeholders `{0}`, `{1}` etc. are preserved
- Reports mismatched placeholder counts

### Loading Validation
- Checks file format correctness
- Reports parsing errors
- Falls back to embedded translations if files fail

## Technical Implementation

### Unicode Display Strategy
The application uses a **hybrid approach** for optimal Unicode support:

- **QLabel Components**: UI titles, labels, and static text use PyQt5 QLabel widgets
  - Native Unicode support without configuration
  - Automatic system font selection
  - Cross-platform compatibility

- **Matplotlib Components**: Graphics overlays, object labels, and annotations use matplotlib
  - Fallback to simplified text if Unicode fails
  - Graceful degradation for unsupported characters

### Benefits of Hybrid Approach
- **Reliability**: Works out-of-the-box on all platforms
- **Performance**: No complex font detection or configuration
- **Maintainability**: Simpler codebase with fewer failure points
- **User Experience**: Consistent Unicode display regardless of system configuration

### Translation Not Appearing
1. Check file is in `translations/` directory
2. Verify file encoding is UTF-8
3. Ensure proper TSV format (tabs, not spaces)
4. Check language code matches filename

### Missing Translations
1. Run validation to find missing keys
2. Copy missing keys from `en.tsv`
3. Translate the missing entries

### File Loading Errors
1. Check console output for error messages
2. Verify TSV format is correct
3. Test with a simple text editor that shows tabs
4. Ensure no special characters in key names

## Contributing Translations

### For Open Source Contributors:
1. Fork the repository
2. Add your translation file to `translations/`
3. Test the translation
4. Submit a pull request

### Translation Quality:
- Use natural, fluent language
- Maintain consistency in terminology
- Consider UI space constraints
- Test with actual application usage

## Automated Translation Tools

While automated translation can provide a starting point, manual review is essential because:

1. **Context matters**: UI text needs to be concise and clear
2. **Technical terms**: SAM2-specific terminology requires understanding
3. **UI constraints**: Some translations may be too long for buttons/labels
4. **Cultural adaptation**: Some concepts may need cultural context

## Future Enhancements

Potential improvements to the translation system:

1. **Plural forms**: Support for different plural rules per language
2. **Regional variants**: Support for regional language differences
3. **RTL support**: Right-to-left language support
4. **Translation memory**: Reuse of common translations
5. **Validation tools**: Enhanced validation for UI constraints
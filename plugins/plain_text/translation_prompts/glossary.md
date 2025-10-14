# Plain Text Glossary

This is a glossary for the Plain Text plugin. Add your terms here.

## General Terms

| Original | Translation | Context | Pattern |
|----------|-------------|---------|---------|
|          |             |         |         |

## Tags

Tags in plain text are enclosed in square brackets: [tag]

Common tag formats:
- `[VAR PKNICK(0000)]` - Variable tags with parameters (hexadecimal)
- `[VAR TRNAME(000A)]` - Trainer name variable
- `[VAR BD06(0000)]` - Special formatting tags
- `[tag]` - Simple tags
- `[TAG WITH SPACES]` - Multi-word tags

Important:
- Keep ALL tags unchanged in translation
- Tags are case-sensitive
- Hexadecimal parameters (0000, 000A, etc.) must remain exactly as is
- Tags are highlighted in gray
- Tags do not break across lines

## Special Characters

- `\n` - Line break (splits text into sublines)
- `\r` - Carriage return
- Preserve all special characters in translation

| Tag | Description |
|-----|-------------|
| [VAR PKNICK(xxxx)] | Pokemon nickname variable |
| [VAR TRNAME(xxxx)] | Trainer name variable |
| [VAR BD06(xxxx)] | Battle dialog formatting |

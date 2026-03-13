class LNETHighlightWrappers:
    def __init__(self, editor):
        self.editor = editor
        self.hi = editor.highlight_interface

    def addCriticalProblemHighlight(self, line_number: int):
        self.hi.addCriticalProblemHighlight(line_number)

    def removeCriticalProblemHighlight(self, line_number: int) -> bool:
        return self.hi.removeCriticalProblemHighlight(line_number)

    def clearCriticalProblemHighlights(self):
        self.hi.clearCriticalProblemHighlights()

    def hasCriticalProblemHighlight(self, line_number = None) -> bool:
        return self.hi.hasCriticalProblemHighlight(line_number)

    def addWarningLineHighlight(self, line_number: int):
        self.hi.addWarningLineHighlight(line_number)

    def removeWarningLineHighlight(self, line_number: int) -> bool:
        return self.hi.removeWarningLineHighlight(line_number)

    def clearWarningLineHighlights(self):
        self.hi.clearWarningLineHighlights()

    def hasWarningLineHighlight(self, line_number = None) -> bool:
        return self.hi.hasWarningLineHighlight(line_number)

    def addWidthExceededHighlight(self, line_number: int):
        self.hi.addWidthExceededHighlight(line_number)

    def removeWidthExceededHighlight(self, line_number: int) -> bool:
        return self.hi.removeWidthExceededHighlight(line_number)

    def clearWidthExceededHighlights(self):
        self.hi.clearWidthExceededHighlights()

    def hasWidthExceededHighlight(self, line_number = None) -> bool:
        return self.hi.hasWidthExceededHighlight(line_number)
    
    def addShortLineHighlight(self, line_number: int):
        self.hi.addShortLineHighlight(line_number)

    def removeShortLineHighlight(self, line_number: int) -> bool:
        return self.hi.removeShortLineHighlight(line_number)

    def clearShortLineHighlights(self):
        self.hi.clearShortLineHighlights()

    def hasShortLineHighlight(self, line_number = None) -> bool:
        return self.hi.hasShortLineHighlight(line_number)

    def addEmptyOddSublineHighlight(self, block_number: int):
        self.hi.addEmptyOddSublineHighlight(block_number)

    def removeEmptyOddSublineHighlight(self, block_number: int) -> bool:
        return self.hi.removeEmptyOddSublineHighlight(block_number)

    def clearEmptyOddSublineHighlights(self):
        self.hi.clearEmptyOddSublineHighlights()

    def hasEmptyOddSublineHighlight(self, block_number = None) -> bool:
        return self.hi.hasEmptyOddSublineHighlight(block_number)

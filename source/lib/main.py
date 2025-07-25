# menuTitle: Anchor Dropper


import os
import json
import unicodedata
from pprint import pprint
import ezui
from glyphNameFormatter.reader import n2u
from glyphConstruction import ParseGlyphConstructionListFromString
from mojo.tools import IntersectGlyphWithLine
from mojo.extensions import getExtensionDefault, setExtensionDefault
from mojo.UI import GetFile, PutFile, AskYesNoCancel, dontShowAgainMessage



EXTENSION_STUB = "com.ryanbugden.anchorDropper"
DATA_KEY = EXTENSION_STUB + ".internalData"
PREF_KEY = EXTENSION_STUB + ".preferences"

VALID_GNAMES = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z", "AE", "OE", "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m", "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z", "dotlessi", "dotlessj"]
VALID_ANAMES = ["gravecmb", "circumflexcmb", "macroncmb", "dotaccentcmb", "dieresiscmb", "ringabovecmb", "hungarumlautcmb", "caroncmb", "cedillacmb", "ogonekcmb", "caronSlovak"]
ORGANIZED_GNAMES = {
    "top":    {"a", "c", "e", "g", "h", "n", "o", "r", "s", "u", "w", "y", "z", "dotlessi", "dotlessj", "A", "C", "D", "E", "G", "H", "I", "J", "L", "N", "O", "R", "S", "T", "U", "W", "Y", "Z", "AE", "gravecmb", "circumflexcmb", "macroncmb", "dotaccentcmb", "dieresiscmb", "ringabovecmb", "hungarumlautcmb", "caroncmb"},
    "bottom": {"C", "G", "K", "L", "N", "R", "S", "T", "c", "k", "l", "n", "r", "s", "t", "cedillacmb", "ogonekcmb"},
    "right":  {"L", "d", "l", "t", "caronSlovak"},
    }
ASCENDERS = ["b", "d", "f", "h", "k", "l"]
ORDERED_DIMENSIONS = ["Ascender", "Cap-Height", "X-Height", "Baseline", "Descender"]



def check_lowercase(g_name):
    uni_to_check = n2u(g_name.split(".")[0])
    if not uni_to_check:
        return False
    return unicodedata.category(chr(uni_to_check)) == 'Ll'
    
def guess_y_pos(g_name, anchor_name):
    lowercase = check_lowercase(g_name)
    if "bottom" in anchor_name or "ogonek" in anchor_name:
        return 3  # Baseline
    elif "right" in anchor_name:
        return 0 if lowercase else 1  # Ascender or Cap-Height
    elif "top" in anchor_name:
        if any(suffix in g_name for suffix in [".cap", ".case"]):
            return 1  # Cap-Height 
        elif lowercase:
            if g_name in ASCENDERS:
                return 0  # Ascender
            else:
                return 2  # X-Height
        elif g_name in VALID_ANAMES or "cmb" in g_name:
            return 2  # X-Height
        else:
            return 1  # Cap-Height 
    else:
        return 1  # Cap-Height
    
def append_anchor(g, anchor_name, base_y, adjusted_y):
    # Use the base y (font dimension) to determine x position before adjusting the y.
    intersection = IntersectGlyphWithLine(g, ((-50, base_y),(g.width + 50, base_y)))
    if intersection:
        xs = [x for (x, y) in intersection]
    else:
        xs = [g.width/2]
    x = int((min(xs) + max(xs))/2)
    if "right" in anchor_name:
        x = min(xs) if "_" in anchor_name else max(xs)
    elif "left" in anchor_name:
        x = max(xs) if "_" in anchor_name else min(xs)
    g.appendAnchor(anchor_name, (x, adjusted_y))
    
def convert_gc_to_ad(path):
    '''
    Converts a glyphConstruction file to Anchor Dropper setting data.
    To-do: Import the existing GC lexer to improve this. Probably check first to see if user has GC installed.
    '''
    txt = ""
    with open(path) as file:
        txt = file.read()
    if not txt:
        return
    data = {}
    constructions = ParseGlyphConstructionListFromString(txt)
    bases = []  # List to hold base glyphs
    accents = []  # List to hold accent glyphs

    for construction in constructions:
        # Ignore constructions that don't reference an anchor name
        if "@" not in construction:
            continue
        base_g_name = construction.split()[2]
        accent_name = construction.split()[4]
        anchor_name = construction.split("@")[-1].split()[0].strip(",")

        # Store bases and accents separately
        if (base_g_name, anchor_name) not in bases:
            bases.append((base_g_name, anchor_name))
        if (accent_name, anchor_name) not in accents:
            accents.append((accent_name, anchor_name))

    # Add all bases and accents to data, ensuring bases come first
    for g_name, anchor_name in bases + accents:  # Concatenate bases and accents
        data.setdefault(anchor_name, []).append({
                    'drop_anchor': True,
                    'glyph': g_name,
                    'y_pos': guess_y_pos(g_name, anchor_name),
                    'y_adjust': 0            
                })
    return data
    
    
DEFAULT_DATA = {
    anchor_name: [
        {
            'drop_anchor': g_name in ORGANIZED_GNAMES[anchor_name],
            'glyph': g_name,
            'y_pos': guess_y_pos(g_name, anchor_name),
            'y_adjust': 0
        }
        for g_name in VALID_GNAMES + VALID_ANAMES
    ]
    for anchor_name in ORGANIZED_GNAMES.keys()
}



class AnchorDropper(ezui.WindowController):

    def build(self):
        # MAIN UI
        content = """
        *  HorizontalStack
        > |-----------------------------| @anchorNameTable
        > |                             |
        > |-----------------------------|
        >> (+-)                           @anchorNameTableAddRemoveButton

        > ---
        
        > |--------------------------|    @mainTable
        > | checkbox | glyph | y_pos  |
        > |----------|-------|-------|
        > | A        | 1     | 500   |
        > |          |       |       |
        > |--------------------------|
        >> (+-)                           @mainTableAddRemoveButton
        >> (*)                            @settingsButton
        >> (Clear Anchors... )            @clearAnchorsButton
        >> (Drop Anchors... )             @initialDropAnchorsButton
        """
        
        # Make anchor name table items
        anchor_name_table_items = ["top", "right", "bottom"]
        anchor_name_table_items = [dict(anchorName=name) for name in anchor_name_table_items]
        
        anchor_name_table_w, main_table_w = 150, 400
        main_button_w = 120
        descriptionData = dict(
            clearAnchorsButton=dict(
                width=main_button_w,
            ),
            initialDropAnchorsButton=dict(
                width=main_button_w,
            ),
            anchorNameTable=dict(
                width=anchor_name_table_w,
                items=anchor_name_table_items,
                showColumnTitles=True,
                allowsMultipleSelection=False,
                enableDelete=True,
                columnDescriptions=[
                    dict(
                        identifier="anchorName",
                        title="Anchor Name",
                        editable=True
                    )
                ]
            ),
            mainTable=dict(
                width=main_table_w,
                items=[],
                enableDelete=True,
                allowsSorting=True,
                columnDescriptions=[
                    dict(
                        identifier="drop_anchor",
                        title="Drop",
                        width=30,
                        editable=True,
                        cellDescription=dict(
                            cellType="Checkbox",
                        ),
                    ),
                    dict(
                        identifier="glyph",
                        title="Glyph Name",
                        width=125,
                        editable=True,
                        cellDescription=dict(
                            valueType="string"
                        ),
                    ),
                    dict(
                        identifier="y_pos",
                        title="Y Position",
                        width=80,
                        editable=True,
                        cellDescription=dict(
                            cellType="PopUpButton",
                            cellClassArguments=dict(
                                items=ORDERED_DIMENSIONS
                            ),
                        ),
                    ),
                    dict(
                        identifier="y_adjust",
                        title="Y Adjustment",
                        width=80,
                        editable=True,
                        cellDescription=dict(
                            valueType="integer"
                        ),
                    ),

                ]
            ),
        )
        extra_width = 51  # To avoid vanilla size error: VanillaWarning: The window's initial size is bigger than the `maxSize`.
        self.w = ezui.EZWindow(
            title="Anchor Dropper",
            minSize=(anchor_name_table_w + main_table_w + extra_width, 300),
            size=   (anchor_name_table_w + main_table_w + extra_width, 500),
            maxSize=(anchor_name_table_w + main_table_w + extra_width, 1200),
            content=content,
            descriptionData=descriptionData,
            controller=self
        )
        table = self.w.getItem("mainTable")
        table._table._menuCallback = self.mainTableMenuCallback
        # Cosmetic changes
        self.w.getNSWindow().setTitlebarAppearsTransparent_(True)
        self.w.getItem('settingsButton').getNSButton().setBezelStyle_(11)
        # Setup UI methods for settings window
        self.w.load_data_from_key = self.load_data_from_key
        self.w.get_data = self.get_data
        self.load_data_from_key()
        
        # POPOVER
        content = """
        * TwoColumnForm       @form
        > : Drop Anchor:
        > [X]                 @dropCheckbox
        > : Y Position:
        > ( ...)              @posInput
        > : Y Adjustment:
        > [_0_]               @adjustInput
        
        ---
        
        (Cancel)              @cancelButton
        """
        descriptionData = dict(
            content=dict(
                sizeStyle="small",
            ),
            form=dict(
                titleColumnWidth=78,
                itemColumnWidth=86,
            ),
            posInput=dict(
                items=ORDERED_DIMENSIONS,
            ),
            adjustInput=dict(
                valueType="integer",
                valueIncrement=1,
            ),
            applyButton=dict(
                width='fill',
            ),
            cancelButton=dict(
                width='fill',
            ),
            toggleAddButton=dict(
                width='fill',
            ),
            )
        self.w_over = ezui.EZPopover(
            content=content,
            descriptionData=descriptionData,
            parentAlignment='right',
            controller=self
        )
    
    def started(self):
        self.w.open()
        
    def destroy(self):
        self.save_data()
        
    def load_data(self, data):
        '''Loads provided data.'''
        setExtensionDefault(DATA_KEY, data)
        self.load_data_from_key()
        
    def load_data_from_key(self):
        '''Loads the extension defaults.'''
        self.internal_data = getExtensionDefault(DATA_KEY, fallback=DEFAULT_DATA)
        self.update_anchor_table_items()
        self.update_main_table_items()
        
    def get_data(self):
        return self.internal_data
        
    def save_data(self):
        '''Saves the internal data to the extension defaults, for use when reopening.'''
        self.update_data()
        # pprint(self.internal_data)
        setExtensionDefault(DATA_KEY, self.internal_data)

    def update_data(self):
        '''Updates the internal data based on the UI info.'''
        # Get all anchor names from the anchor name table
        sel = self.w.getItem("anchorNameTable").getSelectedItems()
        if sel:
            sel = sel[0]['anchorName']
            # print("selected anchor name:", sel)
            items = self.w.getItem("mainTable").get()
            self.internal_data[sel] = items
        # Clear out old data
        temp_data = self.internal_data.copy()
        for anchor_name in temp_data:
            if anchor_name not in [item['anchorName'] for item in self.w.getItem("anchorNameTable").get()]:
                self.internal_data.pop(anchor_name)

    def update_anchor_table_items(self):
        table = self.w.getItem("anchorNameTable")
        if self.internal_data.keys():
            table.set([])
            for anchor_name in self.internal_data.keys():
                item = table.makeItem(
                    anchorName=anchor_name, 
                    )
                table.appendItems([item])    
            table.reloadData()  
            # If there are anchor names, select the first
            if table.get():
                table.setSelectedIndexes([0])
            
    def update_main_table_items(self):
        sel = self.w.getItem("anchorNameTable").getSelectedItems()
        if sel:
            self.w.getItem("mainTableAddRemoveButton").enable(True)
            sel = sel[0]['anchorName']
            if sel in self.internal_data.keys():
                items = self.internal_data[sel]
            else:
                items = self.internal_data[sel] = []
            self.w.getItem("mainTable").set(items)
        else:
            self.w.getItem("mainTable").set([])
            self.w.getItem("mainTableAddRemoveButton").enable(False)
            
    def anchorNameTableSelectionCallback(self, sender):
        self.update_main_table_items()
        
    def anchorNameTableAddRemoveButtonAddCallback(self, sender):
        table = self.w.getItem("anchorNameTable")
        item = table.makeItem(
            anchorName="(Anchor Name)", 
            )
        table.appendItems([item])
        self.update_main_table_items()
        
    def anchorNameTableAddRemoveButtonRemoveCallback(self, sender):
        table = self.w.getItem("anchorNameTable")
        table.removeSelectedItems()
        self.update_data()
        self.update_main_table_items()
        
    def anchorNameTableDeleteCallback(self, sender):
        table = self.w.getItem("anchorNameTable")
        table.removeSelectedItems()
        self.update_data()
        self.update_main_table_items()
        
    def mainTableAddRemoveButtonAddCallback(self, sender):
        table = self.w.getItem("mainTable")
        item = table.makeItem(
            drop_anchor=True, 
            glyph="(Glyph Name)", 
            y_pos=2,
            y_adjust=0,
            )
        table.appendItems([item])
        self.update_data()

    def mainTableAddRemoveButtonRemoveCallback(self, sender):
        table = self.w.getItem("mainTable")
        table.removeSelectedItems()
        self.update_data()
        
    def mainTableDeleteCallback(self, sender):
        table = self.w.getItem("mainTable")
        table.removeSelectedItems()
        self.update_data()
        
    def mainTableMenuCallback(self, sender):
        table = self.w.getItem("mainTable")
        indexes = table.getSelectedIndexes()
        if indexes:
            target_index = int((min(indexes) + max(indexes)) / 2) + 1
            target_index = min([target_index, 7])
            # Predict correct y-pos
            sel_item = table.getSelectedItems()[0]
            self.w_over.getItem("dropCheckbox").set(sel_item['drop_anchor'])
            self.w_over.getItem("posInput").set(sel_item['y_pos'])
            self.w_over.getItem("adjustInput").set(int(sel_item['y_adjust']))
            table.openPopoverAtIndex(self.w_over, target_index)
        
    def initialDropAnchorsButtonCallback(self, sender):
        self.save_data()
        if CurrentFont():
            DropAnchorsController(self.w)
        else:
            dontShowAgainMessage(
                messageText='UFO Needed', 
                informativeText='You must have a UFO open in order to drop some anchors.', 
                alertStyle=1, 
                parentWindow=self.w, 
                resultCallback=None, 
                dontShowAgainKey=''
                )

    def cancelButtonCallback(self, sender):
        self.w_over.close()
        
    def posInputCallback(self, sender):
        table = self.w.getItem("mainTable")
        indexes = table.getSelectedIndexes()
        if indexes:
            # Get current table data
            table_data = table.get()
            for i in indexes:
                table_data[i]["y_pos"] = sender.get()
            # Update table with new data
            table.set(table_data)
            table.reloadData(indexes)
            # Reselect indexes
            table.setSelectedIndexes(indexes)
            self.update_data()

    def adjustInputCallback(self, sender):
        table = self.w.getItem("mainTable")
        indexes = table.getSelectedIndexes()
        if indexes:
            # Get current table data
            table_data = table.get()
            for i in indexes:
                table_data[i]["y_adjust"] = sender.get()
            # Update table with new data
            table.set(table_data)
            table.reloadData(indexes)
            # Reselect indexes
            table.setSelectedIndexes(indexes)
            self.update_data()
            
    def dropCheckboxCallback(self, sender):
        table = self.w.getItem("mainTable")
        indexes = table.getSelectedIndexes()
        if indexes:
            # Get current table data
            table_data = table.get()
            for i in indexes:
                table_data[i]["drop_anchor"] = sender.get()
            # Update table with new data
            table.set(table_data)
            table.reloadData(indexes)
            # Reselect indexes
            table.setSelectedIndexes(indexes)
            self.update_data()
        
    def clearAnchorsButtonCallback(self, sender):
        if CurrentFont():
            ClearAnchorsController(self.w)
        else:
            dontShowAgainMessage(
                messageText='UFO Needed', 
                informativeText='You must have a UFO open in order to clear its anchors.', 
                alertStyle=1, 
                parentWindow=self.w, 
                resultCallback=None, 
                dontShowAgainKey=''
                )

    def settingsButtonCallback(self, sender):
        PreferencesController(self.w)
        


class PreferencesController(ezui.WindowController):

    def build(self, parent):
        self.parent = parent
        content = """
        
        * VerticalStack                   @stack
        
        > (Save Settings)                 @saveSettingsButton
        > (Load Settings)                 @loadSettingsButton
        > (Reset Defaults)                @resetDefaultsButton
        
        > ---
        ===
        (Close)                           @closeButton
        """
        window_width = 150
        settings_button_height = 20
        descriptionData = dict(
            closeButton=dict(
                width=window_width,
                keyEquivalent=chr(27)  # call button on esc keydown
                ),
            saveSettingsButton=dict(
                width='fill',
                height=settings_button_height,
                sizeStyle='regular'
                ),
            loadSettingsButton=dict(
                width='fill',
                height=settings_button_height,
                sizeStyle='regular'
                ),
            resetDefaultsButton=dict(
                width='fill',
                height=settings_button_height,
                sizeStyle='regular'
                ),
            )
        self.w = ezui.EZSheet(
            content=content,
            size='auto',
            descriptionData=descriptionData,
            parent=parent,
            controller=self
        )
        self.w.setDefaultButton(self.w.getItem("closeButton"))
        
    def started(self):
        self.w.open()
        
    def closeButtonCallback(self, sender):
        self.w.close()
        
    def saveSettingsButtonCallback(self, sender):
        data = self.parent.get_data()
        file_name = "settings"
        ext = "anchorDropperSettings"
        f = CurrentFont()
        if f and f.path:
            file_name = os.path.splitext(os.path.basename(f.path))[0]
        path = PutFile(
                    message="Save Anchor Dropper settings.",
                    fileName=f"{file_name}.{ext}"
                    )
        if path.split(".")[-1] != ext:
            path = path.rstrip(".") + "." + ext
        if not path:
            return
        with open(path, "w") as j:
            json.dump(
                data,
                j,
                indent=4,
                # Normalize from NS objects into json-compatible things
                default=lambda o: dict(o) if hasattr(o, "items")
                                    else list(o) if hasattr(o, "__iter__")
                                    else str(o)
            )
        self.w.close()
        
    def loadSettingsButtonCallback(self, sender):
        current_data = self.parent.get_data().copy()
        path = GetFile(
                    message="Select a .anchorDropperSettings or .glyphConstruction file to load a setup.", 
                    title="Load Settings File", 
                    fileTypes=["anchorDropperSettings", "json", "glyphConstruction"]
                    )
        new_data = ""
        if not path:
            return
        if os.path.splitext(path)[-1] in [".anchorDropperSettings", ".json"]:
            with open(path, "r") as j:
                new_data = json.load(j)
        elif os.path.splitext(path)[-1] == ".glyphConstruction":
            new_data = convert_gc_to_ad(path)
        if not new_data:
            return
        overwrite = AskYesNoCancel(
                    message="Importing settings.\nOverwrite the current settings?", 
                    title='Overwrite Settings?', 
                    default=0, 
                    informativeText='Click Yes to replace current settings with imported settings. Click No to add imported settings to current settings.'
                    )
        if overwrite:
            data = new_data
        else:
            for anchor, details in new_data.items():
                if anchor not in current_data:
                    current_data[anchor] = []
                for detail in details:
                    if detail not in current_data[anchor]:
                        current_data[anchor].append(detail)
            data = current_data
        self.load_data(data)
        self.w.close()
        
    def resetDefaultsButtonCallback(self, sender):
        self.load_data(DEFAULT_DATA)
        self.w.close()
        
    def load_data(self, data):
        setExtensionDefault(DATA_KEY, data)
        self.parent.load_data_from_key()
        
        
class ClearAnchorsController(ezui.WindowController):

    def build(self, parent):
        self.parent = parent
        content = """
        (X) Current Font             @fontSelectionRadios                
        ( ) All Fonts

        ---
        
        !* Select and remove anchors by name:
        
        |--------|                   @anchorNameTable
        |        |   
        |--------|   
        
        (Clear All)                  @removeAnchorsButton
        (Clear All Duplicates)       @removeDupesButton

        ===
        * VerticalStack
        > ---
        > (Close)                    @closeButton
        """
        
        anchor_name_table_w = 220
        descriptionData = dict(
            anchorNameTable=dict(
                    width=anchor_name_table_w,
                    items=[],
                    allowsMultipleSelection=True,
                    enableDelete=True,
                ),
            removeAnchorsButton=dict(
                    width=anchor_name_table_w,
                ),
            removeDupesButton=dict(
                    width=anchor_name_table_w,
                ),
            closeButton=dict(
                    width=anchor_name_table_w,
                    keyEquivalent=chr(27)  # call button on esc keydown
                ),
            )
        self.w = ezui.EZSheet(
            content=content,
            size=('auto', 360),
            descriptionData=descriptionData,
            parent=parent,
            controller=self
        )
        self.w.setDefaultButton(self.w.getItem("closeButton"))
        self.fontSelectionRadiosCallback(self.w.getItem("fontSelectionRadios"))
        
    def started(self):
        self.w.open()
        
    def closeButtonCallback(self, sender):
        self.w.close()
        
    def anchorNameTableSelectionCallback(self, sender):
        '''Updates button text based on table selection.'''
        message = "Selected" if sender.getSelectedItems() else "All"
        self.w.getItem("removeAnchorsButton").setTitle(f"Clear {message}")
        self.w.getItem("removeDupesButton").setTitle(f"Clear {message} Duplicates")
        
    def anchorNameTableDeleteCallback(self, sender):
        self.remove_anchors()
        
    def removeAnchorsButtonCallback(self, sender):
        self.remove_anchors()
        
    def remove_anchors(self):
        table = self.w.getItem("anchorNameTable")
        if not table.getSelectedItems():
            # If no selection, remove all
            table.set([])
        table.removeSelectedItems()
        # Delete those anchors
        removed = {}
        for f in self.fonts:
            font_name = " ".join([f.info.familyName, f.info.styleName])
            removed[font_name] = {}
            for g in f:
                for a in g.anchors:
                    if a.name.lstrip('_') not in table.get():
                        g.removeAnchor(a)
                        if g == CurrentGlyph():
                            g.changed()
                        removed[font_name].setdefault(a.name, []).append(g.name)
            f.changed()
        star_length = 40 
        print()
        print("*"*star_length)
        print("Anchor Dropper Anchor Removal Report")
        print("-"*star_length)
        if removed:
            print("Removed the following anchors:")
            pprint(removed)
        else:
            print("Didn't remove any anchors.")
        print("*"*star_length)
        
    def removeDupesButtonCallback(self, sender):
        table = self.w.getItem("anchorNameTable")
        names = table.getSelectedItems() if table.getSelectedItems() else table.get()
        removed = {}
        for f in self.fonts:
            font_name = " ".join([f.info.familyName, f.info.styleName])
            removed[font_name] = {}
            for g in f:
                uniques = []
                for a in g.anchors:
                    if a.name.lstrip('_') not in names:
                        continue
                    if a.name not in uniques:
                        uniques.append(a.name)
                    else:
                        g.removeAnchor(a)
                        if g == CurrentGlyph():
                            g.changed()
                        removed[font_name].setdefault(a.name, []).append(g.name)
            f.changed()
        star_length = 40 
        print()
        print("*"*star_length)
        print("Anchor Dropper Duplicate Removal Report")
        print("-"*star_length)
        if any(removed[font_name] for font_name in removed):
            print("Removed the following anchors:")
            pprint(removed)
        else:
            if table.getSelectedItems():
                print(f"There were no duplicate anchors with names: {names}.")
            else:
                print(f"There were no duplicate anchors.")
        print("*"*star_length)
        
        
    def fontSelectionRadiosCallback(self, sender):
        # Update the list when the radios are changed
        font_span = [[CurrentFont()], AllFonts()]
        self.fonts = font_span[sender.get()]
        self.update_anchor_table_items()
        
        
    def update_anchor_table_items(self):
        anchor_names = set([a.name.lstrip('_') for f in self.fonts for g in f for a in g.anchors])
        table = self.w.getItem("anchorNameTable")
        table.set(anchor_names)
        table.reloadData()



class DropAnchorsController(ezui.WindowController):

    def build(self, parent):
        self.parent = parent
        content = """
        * VerticalStack              @mainVerticalStack
        
        > (X) Current Font           @fontSelectionRadios                
        > ( ) All Fonts
        
        > ---
        > [X] Overwrite              @overwriteCheckbox  
        ===
        * VerticalStack
        > (Drop Anchors)             @dropAnchorsButton
        > (Close)                    @closeButton
        """
        
        item_width = 140
        descriptionData = dict(
            overwriteCheckbox=dict(
                width=item_width
                ),
            dropAnchorsButton=dict(
                    width=item_width,
                ),
            closeButton=dict(
                    width=item_width,
                    keyEquivalent=chr(27)  # call button on esc keydown
                ),
            )
        self.w = ezui.EZSheet(
            content=content,
            size='auto',
            descriptionData=descriptionData,
            parent=parent,
            controller=self
        )
        prefs = getExtensionDefault(PREF_KEY, fallback=self.w.getItemValues())
        try: self.w.setItemValues(prefs)
        except KeyError: pass

        self.w.setDefaultButton(self.w.getItem("dropAnchorsButton"))
        self.update_font_span()
        
    def started(self):
        self.w.open()
        
    def update_sheet_prefs(self):
        setExtensionDefault(PREF_KEY, self.w.getItemValues())
        
    def closeButtonCallback(self, sender):
        self.update_sheet_prefs()
        self.w.close()
        
    def overwriteCheckboxCallback(self, sender):
        self.update_sheet_prefs()
        
    def fontSelectionRadiosCallback(self, sender):
        self.update_font_span()
        self.update_sheet_prefs()

    def update_font_span(self):
        font_span = [[CurrentFont()], AllFonts()]
        self.fonts = font_span[self.w.getItem("fontSelectionRadios").get()]
        
    def dropAnchorsButtonCallback(self, sender):
        if not self.fonts:
            print("Please open a UFO first.")
            return
        self.internal_data = getExtensionDefault(DATA_KEY, {})
        star_length = 40 
        print()
        print("*"*star_length)
        print("Anchor Dropper Report")
        print("-"*star_length)
        for f in self.fonts:
            print(f"{f.info.familyName} {f.info.styleName}")
            print("-"*star_length)
            report = {}
            overwrite = getExtensionDefault(PREF_KEY, fallback={'overwriteCheckbox': 0})['overwriteCheckbox']
            local_dimensions = [f.info.ascender, f.info.capHeight, f.info.xHeight, 0, f.info.descender]
            for anchor_name, data in self.internal_data.items():
                for item in data:
                    drop_anchor, g_name, y_pos, y_adjust = item['drop_anchor'], item['glyph'], item['y_pos'], item['y_adjust']
                    if drop_anchor and g_name in f.keys():
                        g = f[g_name]
                        base_y = local_dimensions[y_pos]
                        adjusted_y = base_y + int(y_adjust)
                        prefix = ""
                        if g_name in VALID_ANAMES or "cmb" in g_name: 
                            prefix = "_"
                        final_anchor_name = prefix + anchor_name
                        if overwrite or final_anchor_name not in [a.name for a in g.anchors]:
                            if overwrite:
                                for a in g.anchors:
                                    if a.name == final_anchor_name:
                                        g.removeAnchor(a)
                                        break
                            append_anchor(g, final_anchor_name, base_y, adjusted_y)
                            report.setdefault(final_anchor_name, []).append((g.name, adjusted_y))
            f.changed()
            if report:
                print("Dropped the following anchors:")
                pprint(report)
                print()
            else:
                print("Didn't drop any new anchors.")
                print()
            print("*"*star_length)
        self.w.close()
        

    
AnchorDropper()

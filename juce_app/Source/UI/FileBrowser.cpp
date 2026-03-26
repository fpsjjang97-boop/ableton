#include "FileBrowser.h"

//==============================================================================
// FileTreeItem
//==============================================================================
FileTreeItem::FileTreeItem (const juce::File& f, bool isDirectory)
    : file (f), isDir (isDirectory)
{
}

void FileTreeItem::paintItem (juce::Graphics& g, int width, int height)
{
    if (isSelected())
    {
        g.setColour (MetallicLookAndFeel::bgSelected);
        g.fillRect (0, 0, width, height);
    }

    // Icon
    auto iconArea = juce::Rectangle<int> (4, 2, height - 4, height - 4);
    g.setColour (isDir ? MetallicLookAndFeel::textDim : MetallicLookAndFeel::accent);

    if (isDir)
    {
        // Folder icon
        juce::Path folder;
        auto r = iconArea.toFloat().reduced (1.0f);
        folder.addRoundedRectangle (r.getX(), r.getY() + r.getHeight() * 0.2f,
                                     r.getWidth(), r.getHeight() * 0.8f, 1.5f);
        folder.addRoundedRectangle (r.getX(), r.getY(),
                                     r.getWidth() * 0.5f, r.getHeight() * 0.35f, 1.5f);
        g.fillPath (folder);
    }
    else
    {
        // File icon
        auto r = iconArea.toFloat().reduced (2.0f);
        g.drawRoundedRectangle (r, 1.0f, 1.0f);
        g.drawHorizontalLine ((int) (r.getY() + r.getHeight() * 0.35f),
                               r.getX() + 2.0f, r.getRight() - 2.0f);
    }

    // Text
    g.setColour (isSelected() ? MetallicLookAndFeel::accentLight : MetallicLookAndFeel::textPrimary);
    g.setFont (juce::Font (12.0f));
    g.drawText (file.getFileName(),
                iconArea.getRight() + 4, 0, width - iconArea.getRight() - 8, height,
                juce::Justification::centredLeft, true);
}

void FileTreeItem::itemOpennessChanged (bool isNowOpen)
{
    if (isNowOpen && isDir && getNumSubItems() == 0)
    {
        // Lazy-load directory contents
        auto files = file.findChildFiles (juce::File::findFilesAndDirectories, false);
        files.sort();

        // Directories first
        for (auto& f : files)
        {
            if (f.isDirectory())
            {
                auto* item = new FileTreeItem (f, true);
                item->onFileDoubleClicked = onFileDoubleClicked;
                item->onFileSelected = onFileSelected;
                addSubItem (item);
            }
        }
        for (auto& f : files)
        {
            if (! f.isDirectory())
            {
                auto* item = new FileTreeItem (f, false);
                item->onFileDoubleClicked = onFileDoubleClicked;
                item->onFileSelected = onFileSelected;
                addSubItem (item);
            }
        }
    }
    else if (! isNowOpen)
    {
        clearSubItems();
    }
}

void FileTreeItem::itemDoubleClicked (const juce::MouseEvent&)
{
    if (! isDir && onFileDoubleClicked)
        onFileDoubleClicked (file);
}

void FileTreeItem::itemSelectionChanged (bool isNowSelected)
{
    if (isNowSelected && onFileSelected)
        onFileSelected (file);
}

//==============================================================================
// FileBrowser
//==============================================================================
FileBrowser::FileBrowser()
{
    // Search box
    searchBox.setTextToShowWhenEmpty ("Search files...", MetallicLookAndFeel::textDim);
    searchBox.setFont (juce::Font (12.0f));
    searchBox.addListener (this);
    addAndMakeVisible (searchBox);

    // Category buttons
    struct CatInfo { const char* name; Category cat; };
    CatInfo cats[] = {
        { "All",      AllFiles },
        { "MIDI",     MidiFiles },
        { "Projects", Projects },
        { "Audio",    AudioFiles },
        { "Presets",  Presets },
        { "Output",   Output }
    };

    for (auto& c : cats)
    {
        auto* btn = categoryButtons.add (new juce::TextButton (c.name));
        btn->setColour (juce::TextButton::buttonColourId, MetallicLookAndFeel::bgMid);
        btn->setColour (juce::TextButton::buttonOnColourId, MetallicLookAndFeel::bgSelected);
        btn->setClickingTogglesState (true);
        btn->setRadioGroupId (1001);
        auto cat = c.cat;
        btn->onClick = [this, cat]() { setCategory (cat); };
        addAndMakeVisible (btn);
    }
    if (! categoryButtons.isEmpty())
        categoryButtons[0]->setToggleState (true, juce::dontSendNotification);

    // Tree view
    treeView.setColour (juce::TreeView::backgroundColourId, MetallicLookAndFeel::bgPanel);
    treeView.setDefaultOpenness (false);
    treeView.setMultiSelectEnabled (false);
    treeView.setRootItemVisible (false);
    addAndMakeVisible (treeView);

    // File info
    fileInfoLabel.setFont (juce::Font (10.0f));
    fileInfoLabel.setColour (juce::Label::textColourId, MetallicLookAndFeel::textDim);
    fileInfoLabel.setJustificationType (juce::Justification::centredLeft);
    addAndMakeVisible (fileInfoLabel);

    // Default root
    rootDirectory = juce::File::getSpecialLocation (juce::File::userDocumentsDirectory);
}

void FileBrowser::paint (juce::Graphics& g)
{
    g.fillAll (MetallicLookAndFeel::bgPanel);

    // Title
    g.setColour (MetallicLookAndFeel::textSecondary);
    g.setFont (juce::Font (11.0f, juce::Font::bold));
    g.drawText ("FILES", 8, 4, 80, 16, juce::Justification::centredLeft);

    // Border
    g.setColour (MetallicLookAndFeel::border);
    g.drawVerticalLine (getWidth() - 1, 0.0f, (float) getHeight());
}

void FileBrowser::resized()
{
    auto area = getLocalBounds().reduced (4);
    area.removeFromTop (20); // title space

    searchBox.setBounds (area.removeFromTop (24).reduced (0, 2));
    area.removeFromTop (4);

    // Category buttons in a flow layout
    auto catArea = area.removeFromTop (24);
    int catW = catArea.getWidth() / juce::jmax (1, categoryButtons.size());
    for (auto* btn : categoryButtons)
    {
        btn->setBounds (catArea.removeFromLeft (catW).reduced (1));
    }
    area.removeFromTop (4);

    // File info at bottom
    fileInfoLabel.setBounds (area.removeFromBottom (20));

    // Tree view takes remaining space
    treeView.setBounds (area);
}

void FileBrowser::setRootDirectory (const juce::File& dir)
{
    rootDirectory = dir;
    populateTree();
}

void FileBrowser::refresh()
{
    populateTree();
}

void FileBrowser::setSearchFilter (const juce::String& filter)
{
    searchFilter = filter.toLowerCase();
    populateTree();
}

void FileBrowser::setCategory (Category cat)
{
    currentCategory = cat;
    populateTree();
}

void FileBrowser::textEditorTextChanged (juce::TextEditor& editor)
{
    if (&editor == &searchBox)
        setSearchFilter (editor.getText());
}

juce::String FileBrowser::getExtensionFilter() const
{
    switch (currentCategory)
    {
        case MidiFiles:   return "*.mid;*.midi";
        case Projects:    return "*.maw;*.xml";
        case AudioFiles:  return "*.wav;*.mp3;*.ogg;*.flac;*.aiff";
        case Presets:     return "*.json;*.preset";
        case Output:      return "*.wav;*.mid;*.midi";
        default:          return "*";
    }
}

void FileBrowser::populateTree()
{
    treeView.setRootItem (nullptr);

    rootItem = std::make_unique<FileTreeItem> (rootDirectory, true);
    rootItem->onFileDoubleClicked = [this] (const juce::File& f)
    {
        if (onFileDoubleClicked) onFileDoubleClicked (f);
    };
    rootItem->onFileSelected = [this] (const juce::File& f)
    {
        // Update info label
        juce::String info = f.getFileName();
        if (! f.isDirectory())
        {
            auto sizeKB = f.getSize() / 1024;
            info += " (" + juce::String (sizeKB) + " KB)";
        }
        fileInfoLabel.setText (info, juce::dontSendNotification);

        if (onFileSelected) onFileSelected (f);
    };

    treeView.setRootItem (rootItem.get());
    rootItem->setOpen (true);
}

void FileBrowser::addFilesToItem (FileTreeItem* parent, const juce::File& dir)
{
    auto files = dir.findChildFiles (juce::File::findFilesAndDirectories, false);
    files.sort();

    for (auto& f : files)
    {
        if (f.isDirectory())
        {
            auto* item = new FileTreeItem (f, true);
            item->onFileDoubleClicked = onFileDoubleClicked;
            item->onFileSelected = [this] (const juce::File& file)
            {
                if (onFileSelected) onFileSelected (file);
            };
            parent->addSubItem (item);
        }
        else
        {
            // Apply filters
            if (searchFilter.isNotEmpty() &&
                ! f.getFileName().toLowerCase().contains (searchFilter))
                continue;

            auto ext = getExtensionFilter();
            if (ext != "*")
            {
                bool matches = false;
                juce::StringArray exts;
                exts.addTokens (ext, ";", "");
                for (auto& e : exts)
                {
                    if (f.hasFileExtension (e.fromFirstOccurrenceOf ("*", false, false)))
                    {
                        matches = true;
                        break;
                    }
                }
                if (! matches) continue;
            }

            auto* item = new FileTreeItem (f, false);
            item->onFileDoubleClicked = onFileDoubleClicked;
            item->onFileSelected = [this] (const juce::File& file)
            {
                if (onFileSelected) onFileSelected (file);
            };
            parent->addSubItem (item);
        }
    }
}

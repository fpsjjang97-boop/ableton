#pragma once
#include <JuceHeader.h>
#include "LookAndFeel.h"

//==============================================================================
// FileTreeItem - TreeViewItem for the file browser
//==============================================================================
class FileTreeItem : public juce::TreeViewItem
{
public:
    FileTreeItem (const juce::File& file, bool isDirectory);

    bool mightContainSubItems() override       { return isDir; }
    bool canBeSelected() const override        { return true; }
    juce::String getUniqueName() const override { return file.getFullPathName(); }

    void paintItem (juce::Graphics& g, int width, int height) override;
    void itemOpennessChanged (bool isNowOpen) override;
    void itemDoubleClicked (const juce::MouseEvent& e) override;
    void itemSelectionChanged (bool isNowSelected) override;

    const juce::File& getFile() const { return file; }

    std::function<void (const juce::File&)> onFileDoubleClicked;
    std::function<void (const juce::File&)> onFileSelected;

private:
    juce::File file;
    bool isDir;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (FileTreeItem)
};

//==============================================================================
// FileBrowser - File browser panel
//==============================================================================
class FileBrowser : public juce::Component,
                    public juce::TextEditor::Listener
{
public:
    FileBrowser();
    ~FileBrowser() override = default;

    void paint (juce::Graphics& g) override;
    void resized() override;

    void setRootDirectory (const juce::File& dir);
    void refresh();
    void setSearchFilter (const juce::String& filter);

    // ── Category list ───────────────────────────────────────────────────────
    enum Category { AllFiles, MidiFiles, Projects, AudioFiles, Presets, Output };
    void setCategory (Category cat);

    // ── Callbacks ───────────────────────────────────────────────────────────
    std::function<void (const juce::File&)> onFileDoubleClicked;
    std::function<void (const juce::File&)> onFileSelected;

private:
    // Search
    juce::TextEditor searchBox;

    // Category buttons
    juce::OwnedArray<juce::TextButton> categoryButtons;
    Category currentCategory = AllFiles;

    // Tree view
    juce::TreeView treeView;
    std::unique_ptr<FileTreeItem> rootItem;

    // File info
    juce::Label fileInfoLabel;

    // State
    juce::File rootDirectory;
    juce::String searchFilter;

    void populateTree();
    void addFilesToItem (FileTreeItem* parent, const juce::File& dir);
    void textEditorTextChanged (juce::TextEditor& editor) override;
    juce::String getExtensionFilter() const;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (FileBrowser)
};

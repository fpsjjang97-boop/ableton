#include "PluginEditorWindow.h"

PluginEditorWindow::PluginEditorWindow(juce::AudioPluginInstance& instance,
                                       const juce::String& titleName)
    : juce::DocumentWindow(titleName,
                            juce::Colour(0xFF202020),
                            juce::DocumentWindow::closeButton
                            | juce::DocumentWindow::minimiseButton)
{
    setUsingNativeTitleBar(true);

    if (instance.hasEditor())
        editor.reset(instance.createEditorIfNeeded());
    else
        editor.reset(new juce::GenericAudioProcessorEditor(instance));

    if (editor != nullptr)
    {
        setContentNonOwned(editor.get(), true);
        setResizable(editor->isResizable(), false);
    }
    else
    {
        setSize(320, 120);
    }
}

PluginEditorWindow::~PluginEditorWindow()
{
    clearContentComponent();
    editor.reset();
}

void PluginEditorWindow::closeButtonPressed()
{
    // Caller owns the window via unique_ptr-like pattern (see launch).
    // Hide + auto-delete via setVisible(false) if owned by factory.
    setVisible(false);
    delete this;
}

PluginEditorWindow* PluginEditorWindow::launch(juce::AudioPluginInstance& instance,
                                                const juce::String& title)
{
    auto* w = new PluginEditorWindow(instance, title);
    w->setVisible(true);
    w->centreWithSize(w->getWidth() > 0 ? w->getWidth() : 400,
                      w->getHeight() > 0 ? w->getHeight() : 300);
    return w;
}

// ---------------------------------------------------------------------------
// PluginEditorManager (V5)
// ---------------------------------------------------------------------------
PluginEditorManager& PluginEditorManager::instance()
{
    static PluginEditorManager mgr;
    return mgr;
}

PluginEditorWindow* PluginEditorManager::openFor(int trackId, int slotIdx,
                                                  juce::AudioPluginInstance& inst,
                                                  const juce::String& title)
{
    // If one already exists for this (trackId, slotIdx), bring it to front.
    for (auto& ptr : windows)
    {
        if (ptr == nullptr) continue;
        if (ptr->ownerTrackId == trackId && ptr->ownerSlotIdx == slotIdx)
        {
            ptr->toFront(true);
            return ptr;
        }
    }

    auto* w = PluginEditorWindow::launch(inst, title);
    w->ownerTrackId = trackId;
    w->ownerSlotIdx = slotIdx;
    windows.push_back(w);
    return w;
}

void PluginEditorManager::closeAllForTrack(int trackId)
{
    for (auto& ptr : windows)
    {
        if (ptr == nullptr) continue;
        if (ptr->ownerTrackId == trackId)
            ptr->closeButtonPressed(); // self-deletes
    }
    // Compact dangling SafePointers
    windows.erase(std::remove_if(windows.begin(), windows.end(),
        [](const juce::Component::SafePointer<PluginEditorWindow>& p)
        { return p == nullptr; }), windows.end());
}

void PluginEditorManager::closeAll()
{
    for (auto& ptr : windows)
        if (ptr != nullptr) ptr->closeButtonPressed();
    windows.clear();
}

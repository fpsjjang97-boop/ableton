#include "PluginBrowser.h"

PluginBrowser::PluginBrowser(PluginHost& host, SelectCallback onSelect)
    : pluginHost(host), selectCallback(std::move(onSelect))
{
    pathField.setMultiLine(false);
    pathField.setReturnKeyStartsNewLine(false);
    pathField.setText(PluginHost::getDefaultVst3SearchPaths().toString());
    addAndMakeVisible(pathField);

    scanButton.onClick   = [this] { doScan(); };
    defaultsBtn.onClick  = [this] { pathField.setText(PluginHost::getDefaultVst3SearchPaths().toString()); };
    okButton.onClick     = [this] { useSelected(); };
    cancelButton.onClick = [this] { if (auto* dw = findParentComponentOfClass<juce::DialogWindow>()) dw->exitModalState(0); };

    addAndMakeVisible(scanButton);
    addAndMakeVisible(defaultsBtn);
    addAndMakeVisible(okButton);
    addAndMakeVisible(cancelButton);

    pluginList.setModel(this);
    pluginList.setRowHeight(22);
    addAndMakeVisible(pluginList);

    statusLabel.setText(juce::String(pluginHost.getKnownList().getNumTypes())
                        + " plugins known", juce::dontSendNotification);
    addAndMakeVisible(statusLabel);

    setSize(640, 480);
}

void PluginBrowser::resized()
{
    auto r = getLocalBounds().reduced(8);

    auto top = r.removeFromTop(28);
    pathField.setBounds(top.removeFromLeft(top.getWidth() - 180));
    top.removeFromLeft(4);
    defaultsBtn.setBounds(top.removeFromLeft(80));
    top.removeFromLeft(4);
    scanButton.setBounds(top);

    r.removeFromTop(6);

    auto bottom = r.removeFromBottom(32);
    cancelButton.setBounds(bottom.removeFromRight(80));
    bottom.removeFromRight(6);
    okButton.setBounds(bottom.removeFromRight(80));
    statusLabel.setBounds(bottom);

    r.removeFromBottom(6);
    pluginList.setBounds(r);
}

void PluginBrowser::doScan()
{
    juce::FileSearchPath paths;
    paths.addPath(pathField.getText());

    statusLabel.setText("Scanning...", juce::dontSendNotification);
    repaint();

    int added = pluginHost.scanForPlugins(paths);

    statusLabel.setText(juce::String(added) + " new, "
                        + juce::String(pluginHost.getKnownList().getNumTypes())
                        + " total", juce::dontSendNotification);
    pluginList.updateContent();
    pluginList.repaint();
}

void PluginBrowser::useSelected()
{
    int row = pluginList.getSelectedRow();
    auto& types = pluginHost.getKnownList().getTypes();
    if (row < 0 || row >= types.size()) return;

    if (selectCallback) selectCallback(types[row]);
    if (auto* dw = findParentComponentOfClass<juce::DialogWindow>())
        dw->exitModalState(1);
}

int PluginBrowser::getNumRows()
{
    return pluginHost.getKnownList().getNumTypes();
}

void PluginBrowser::paintListBoxItem(int row, juce::Graphics& g,
                                      int width, int height, bool selected)
{
    auto& types = pluginHost.getKnownList().getTypes();
    if (row < 0 || row >= types.size()) return;
    auto& d = types[row];

    g.fillAll(selected ? juce::Colour(0xFF2A4A6A) : juce::Colour(0xFF1A1A1A));
    g.setColour(juce::Colours::white);
    g.setFont(12.0f);
    g.drawText(d.name + "  [" + d.pluginFormatName + "]  "
               + d.manufacturerName,
               6, 0, width - 12, height,
               juce::Justification::centredLeft);
}

void PluginBrowser::listBoxItemDoubleClicked(int, const juce::MouseEvent&)
{
    useSelected();
}

void PluginBrowser::launchModal(PluginHost& host, SelectCallback onSelect)
{
    auto* browser = new PluginBrowser(host, std::move(onSelect));

    juce::DialogWindow::LaunchOptions opts;
    opts.dialogTitle                  = "Plugin Browser";
    opts.content.setOwned(browser);
    opts.dialogBackgroundColour       = juce::Colour(0xFF101010);
    opts.escapeKeyTriggersCloseButton = true;
    opts.useNativeTitleBar            = true;
    opts.resizable                    = true;
    opts.launchAsync();
}

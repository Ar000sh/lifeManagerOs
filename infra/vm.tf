resource "azurerm_linux_virtual_machine" "main" {
  name                            = "vm-${var.prefix}"
  resource_group_name             = azurerm_resource_group.main.name
  location                        = azurerm_resource_group.main.location
  size                            = var.vm_size
  admin_username                  = "azureuser"
  network_interface_ids           = [azurerm_network_interface.vm.id]
  disable_password_authentication = true

  admin_ssh_key {
    username   = "azureuser"
    public_key = var.ssh_public_key
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts-gen2"
    version   = "latest"
  }

  # System-assigned Managed Identity: the VM gets an Azure AD identity with no
  # stored credentials. We grant THAT identity access to Key Vault + ACR below.
  identity {
    type = "SystemAssigned"
  }

  # cloud-init script, templated with the names the VM needs at boot.
  custom_data = base64encode(templatefile("${path.module}/cloud-init.yaml.tftpl", {
    acr_name         = azurerm_container_registry.main.name
    acr_login_server = azurerm_container_registry.main.login_server
    kv_name          = azurerm_key_vault.main.name
  }))
}

# The VM identity may READ secrets from the vault (not write — least privilege).
resource "azurerm_role_assignment" "vm_kv" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_linux_virtual_machine.main.identity[0].principal_id
}

# The VM identity may PULL images from ACR (not push).
resource "azurerm_role_assignment" "vm_acr" {
  scope                = azurerm_container_registry.main.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_linux_virtual_machine.main.identity[0].principal_id
}

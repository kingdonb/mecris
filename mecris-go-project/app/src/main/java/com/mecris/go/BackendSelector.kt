package com.mecris.go

import android.content.Context
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.mecris.go.BackendManager

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BackendSelector(onBackendChanged: () -> Unit) {
    val context = LocalContext.current
    var expanded by remember { mutableStateOf(false) }
    var selectedUrl by remember { mutableStateOf(BackendManager.getBaseUrl(context)) }
    val selectedName = BackendManager.ENDPOINTS.find { it.second == selectedUrl }?.first ?: "Custom"

    ExposedDropdownMenuBox(
        expanded = expanded,
        onExpandedChange = { expanded = !expanded },
        modifier = Modifier.fillMaxWidth()
    ) {
        OutlinedTextField(
            value = selectedName,
            onValueChange = {},
            readOnly = true,
            label = { Text("Mecris Backend Server") },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
            colors = ExposedDropdownMenuDefaults.outlinedTextFieldColors(),
            modifier = Modifier.menuAnchor().fillMaxWidth()
        )
        ExposedDropdownMenu(
            expanded = expanded,
            onDismissRequest = { expanded = false }
        ) {
            BackendManager.ENDPOINTS.forEach { (name, url) ->
                DropdownMenuItem(
                    text = { Text(name) },
                    onClick = {
                        BackendManager.setBaseUrl(context, url)
                        selectedUrl = url
                        expanded = false
                        onBackendChanged()
                    }
                )
            }
        }
    }
}

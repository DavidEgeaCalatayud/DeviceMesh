package io.github.davidegeacalatayud.devicemesh.feature.dashboard

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import io.github.davidegeacalatayud.devicemesh.core.designsystem.DeviceMeshTheme

@Composable fun DashboardScreen() = DeviceMeshTheme { Surface { Column(Modifier.padding(24.dp)) { Text("DeviceMesh", style = MaterialTheme.typography.headlineLarge); Text("Local-first device observability") } } }

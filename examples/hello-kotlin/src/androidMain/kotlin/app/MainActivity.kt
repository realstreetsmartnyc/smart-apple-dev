package app

import android.app.Activity
import android.os.Bundle
import android.widget.TextView

/**
 * Android entry point. The KMP `commonMain` only exposes a top-level
 * `main()` for desktop/iOS — Android needs an Activity, so we just
 * display the same greeting string in a TextView.
 */
class MainActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val label = TextView(this).apply {
            textSize = 22f
            text = greeting()
        }
        setContentView(label)
    }
}

private fun greeting(): String = "Hello from hello-kotlin!"

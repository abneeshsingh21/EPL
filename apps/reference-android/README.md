# Reference Android App

Reference EPL Android app used for generated-project and Gradle-build validation.

## Generate

```bash
epl android src/main.epl
```

Open the generated project in Android Studio or use the standard Gradle wrapper:

```bash
./gradlew lintDebug testDebugUnitTest assembleDebug assembleRelease
```

On Windows:

```bat
gradlew.bat lintDebug testDebugUnitTest assembleDebug assembleRelease
```

CI contract:

- generates the Android project from `src/main.epl`
- ships the generated project with the standard Gradle wrapper files
- dedicated Android CI job runs real `lintDebug`, `testDebugUnitTest`, `assembleDebug`, and `assembleRelease` validation passes

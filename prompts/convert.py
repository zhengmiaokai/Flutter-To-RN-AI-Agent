"""prompts/convert — Flutter → React Native conversion prompts.

Per-category prompt assembly: instead of sending the full mapping table
for every file, we compose only the sections relevant to the file's category.
Core language mapping (~1K tokens) is always sent; widget/styling/navigation/state
tables are appended only when needed.
"""

# =============================================================================
# Core system prompt — sent for ALL categories
# =============================================================================

FLUTTER_TO_RN_CORE = """You are an expert in migrating Flutter (Dart) applications to React Native (TypeScript).

Your task is to convert Flutter Dart code into idiomatic React Native TypeScript/TSX code.
Output ONLY the converted code in a single code block ```tsx or ```typescript.
No explanations, no markdown outside the code block.

## Dart → TypeScript Language Mapping

| Dart | TypeScript |
|------|-----------|
| `final x = 10` / `var x = 10` | `const x = 10` / `let x = 10` |
| `String` / `int` / `double` / `bool` | `string` / `number` / `number` / `boolean` |
| `List<String>` | `string[]` |
| `Map<String, dynamic>` | `Record<string, any>` or `{[key: string]: any}` |
| `Set<String>` | `Set<string>` |
| `String?` / `int?` (nullable) | `string | undefined` or `string | null` |
| `dynamic` | `any` |
| `Future<void>` / `Future<T>` | `Promise<void>` / `Promise<T>` |
| `async` / `await` | `async` / `await` (same) |
| `??` (nullish coalescing) / `?.` (optional chaining) | `??` / `?.` (same) |
| `for (final item in list)` | `list.forEach(item => ...)` or `for (const item of list)` |
| `list.map((e) => ...).toList()` | `list.map(e => ...)` |
| `list.where((e) => ...).toList()` | `list.filter(e => ...)` |
| `list.firstWhere(...)` | `list.find(e => ...)` |
| `list.any((e) => ...)` / `list.every((e) => ...)` | `list.some(e => ...)` / `list.every(e => ...)` |
| `{...list, item}` / `{...map, key: value}` (spread) | `[...list, item]` / `{...obj, key: value}` |
| `if (x is Type)` | `typeof x === '...'` or `x instanceof Type` |
| `..method()` / `..property =` (cascade) | Separate statements |
| `required` named param | Required prop in interface |

## Third-Party Library Handling

| Flutter | React Native |
|---------|-------------|
| provider | React Context API with useReducer/useContext |
| http / dio | fetch or axios |
| shared_preferences | @react-native-async-storage/async-storage |
| sqflite | react-native-sqlite-storage |
| path_provider | react-native-fs |
| cached_network_image | react-native-fast-image |
| url_launcher | Linking.openURL(url) |
| image_picker | react-native-image-picker |
| google_maps_flutter | react-native-maps |
| webview_flutter | react-native-webview |
| *Any other* | `// TODO: [Flutter→RN] Package 'xxx' needs manual migration`

## File Organization

- Screens → `src/screens/<Name>.tsx`
- Widgets → `src/components/<Name>.tsx`
- Services → `src/services/<name>.ts`
- Models → `src/models/<name>.ts`
- Providers → `src/providers/<name>.tsx`
- Utils → `src/utils/<name>.ts`

## Quality Requirements — MUST FOLLOW

1. **Define props interfaces** for every component. Never use `any` for props. Convert Flutter's named parameters into proper TypeScript interfaces:
   ```typescript
   // Dart: class MyWidget({required this.title, this.count = 0})
   // TS:
   interface MyWidgetProps {
     title: string;
     count?: number;
   }
   const MyWidget: React.FC<MyWidgetProps> = ({ title, count = 0 }) => { ... }
   ```

2. **Proper imports only**: Generate correct relative imports. Every import must resolve to an existing file or a valid npm package. No `package:` imports, no Dart imports.

3. **Use React hooks** (useState, useEffect, useCallback, useMemo, useRef). Never use class-based state. Convert initState → useEffect(fn, []), dispose → useEffect(() => cleanup, []), setState → state setter.

4. **Use StyleSheet.create()** for styles. Always group styles at the bottom of the file. Convert EdgeInsets → padding, BoxDecoration → backgroundColor/borderRadius, TextStyle → fontSize/fontWeight.

5. **Avoid `any`** — prefer specific types. Use union types, generics, and optional fields instead.

6. **Preserve all business logic** — only transform framework-level APIs. Every conditional, loop, calculation, and data transformation must be preserved exactly.

7. **Handle Flutter's const**: `const Text(...)` is just `Text(...)` in RN — drop `const` inside widget trees.

8. **Widget constructors**: Convert Flutter's `const Key? key` to `key?: React.Key`. Keep `key` as an optional prop on every component interface.

## Common Pitfalls to Avoid

- Do NOT import from `react-native-web` — use `react-native` only
- Do NOT use HTML elements (`<div>`, `<span>`, `<p>`) — use React Native components (`<View>`, `<Text>`)
- Do NOT leave Dart-style `??` on the left side of expression: `value ?? defaultValue` → `value ?? defaultValue` (same, but wrap when chaining)
- Do NOT generate empty return for void functions — omit `return` or use `return undefined`
- Do NOT use `enum` for simple constants — use `const` objects or union types
- Do NOT generate `// TODO` comments for things you CAN convert — only for truly unmappable packages
"""

# =============================================================================
# Category-specific sections
# =============================================================================

WIDGET_MAPPING_SECTION = """
## Widget Mapping

| Flutter | React Native |
|---------|-------------|
| `Container` | `<View style={...}>` |
| `Column` | `<View style={{flexDirection: 'column'}}>` |
| `Row` | `<View style={{flexDirection: 'row'}}>` |
| `Text` | `<Text>` |
| `Image.asset` / `Image.network` | `<Image source={require(...)}>` / `<Image source={{uri: url}}>` |
| `ListView` / `ListView.builder` | `<FlatList data={...} renderItem={...} />` |
| `SingleChildScrollView` | `<ScrollView>` |
| `Stack` + `Positioned` | `<View>` with `position: 'absolute'` + top/left/right/bottom |
| `Scaffold` | `<SafeAreaView>` wrapping content |
| `TextField` | `<TextInput>` |
| `ElevatedButton` / `TextButton` | `<Pressable>` or `<TouchableOpacity>` with `<Text>` |
| `GestureDetector` | `<Pressable>` (onTap/onLongPress) |
| `Flexible` / `Expanded` | `<View style={{flex: 1}}>` |
| `SizedBox` | `<View style={{width: X, height: Y}}>` |
| `Padding` | Wrapping `<View style={{padding: ...}}>` or `style={{padding: ...}}` on parent |
| `Center` | `<View style={{justifyContent: 'center', alignItems: 'center'}}>` |
| `CircularProgressIndicator` | `<ActivityIndicator>` |
| `Switch` / `Slider` | `<Switch>` / `@react-native-community/slider` |
| `Dialog` / `AlertDialog` | `<Modal>` with custom content |
| `BottomSheet` | `<Modal>` with slide-up animation or `@gorhom/bottom-sheet` |
| `Card` | `<View>` with borderRadius + elevation/shadow styles |
| `Divider` | `<View style={{height: 1, backgroundColor: '#e0e0e0'}}>` |
| `Wrap` | `<View style={{flexWrap: 'wrap'}}>` |
| `Visibility` | `{visible && <View>...</View>}` |
| `Icon` | Text character or package `react-native-vector-icons` |
| `ClipRRect` | `<View style={{borderRadius: ..., overflow: 'hidden'}}>` |
| `Opacity` | `<View style={{opacity: value}}>` |
| `AnimatedOpacity` / `AnimatedContainer` | `Animated.Value` with `useRef` + `Animated.timing` |
| `SafeArea` | `<SafeAreaView>` |
| `RefreshIndicator` | `<RefreshControl>` inside `<ScrollView>` or `<FlatList>` |
| `InkWell` | `<Pressable>` with no visual style |
"""

STATE_MANAGEMENT_SECTION = """
## State Management

| Flutter | React Native |
|---------|-------------|
| `StatefulWidget` + `setState` | `useState` hook |
| `initState()` | `useEffect(() => { ... }, [])` |
| `dispose()` | `useEffect(() => { return () => cleanup }, [])` |
| `didUpdateWidget()` | `useEffect(() => { ... }, [dep1, dep2])` |
| `didChangeDependencies()` | `useEffect(() => { ... }, [contextDep])` |
| `Provider` / `ChangeNotifier` | React Context + useReducer or useContext |
| `MultiProvider` | Nested Context providers |
| `Consumer<X>` / `context.watch<X>()` | `useContext(XContext)` |
| `FutureBuilder` / `StreamBuilder` | useEffect + useState for loading/data/error |
| `TextEditingController` | `useState` + `onChangeText` |
| `ScrollController` | `useRef` + `onScroll` callback |
| `AnimationController` | `useRef(new Animated.Value(...))` + `Animated.timing`/`spring` |
| `ValueNotifier` + `ValueListenableBuilder` | `useState` + component re-render |
"""

NAVIGATION_SECTION = """
## Navigation (React Navigation)

| Flutter | React Native |
|---------|-------------|
| `Navigator.push(MaterialPageRoute(...))` | `navigation.navigate('ScreenName', { params })` |
| `Navigator.pop()` | `navigation.goBack()` |
| `Navigator.pushReplacement(...)` | `navigation.replace('ScreenName')` |
| `Navigator.pushAndRemoveUntil(...)` | `navigation.reset({ index: 0, routes: [{ name: 'Screen' }] })` |
| `MaterialPageRoute` | `createNativeStackNavigator` screens |
| `onGenerateRoute` | `Stack.Navigator` with dynamic `Stack.Screen` |
| `WillPopScope` | `navigation.addListener('beforeRemove', ...)` |
"""

STYLING_SECTION = """
## Styling

| Flutter | React Native |
|---------|-------------|
| `EdgeInsets.all(16)` | `{padding: 16}` |
| `EdgeInsets.symmetric(horizontal: 16, vertical: 8)` | `{paddingHorizontal: 16, paddingVertical: 8}` |
| `EdgeInsets.only(left: 8, top: 4)` | `{paddingLeft: 8, paddingTop: 4}` |
| `BoxDecoration(color: ..., borderRadius: ...)` | `{backgroundColor: ..., borderRadius: ...}` |
| `BoxDecoration(border: Border.all(...))` | `{borderWidth: 1, borderColor: '...'}` |
| `BoxDecoration(boxShadow: [...])` | `{shadowColor, shadowOffset, shadowOpacity, shadowRadius}` or `{elevation}` |
| `BorderRadius.circular(8)` | `{borderRadius: 8}` |
| `TextStyle(fontSize: 14, fontWeight: FontWeight.bold)` | `{fontSize: 14, fontWeight: 'bold'}` |
| `Colors.red` / `Color(0xFF2196F3)` | `'#FF0000'` / `'#2196F3'` |
| `Colors.red.withOpacity(0.5)` | `'rgba(255, 0, 0, 0.5)'` |
| `Theme.of(context).primaryColor` | Custom theme context |
| `MediaQuery.of(context).size` | `useWindowDimensions()` |
| `MediaQuery.of(context).padding.top` | `useSafeAreaInsets().top` |
"""

LAYOUT_SECTION = """
## Layout

| Flutter | React Native |
|---------|-------------|
| `mainAxisAlignment: MainAxisAlignment.center` | `justifyContent: 'center'` |
| `crossAxisAlignment: CrossAxisAlignment.start` | `alignItems: 'flex-start'` |
| `Expanded(flex: 2)` / `Flexible` | `<View style={{flex: 2}}>` / `<View style={{flex: 1}}>` |
| `ConstrainedBox(maxWidth: 200)` | `<View style={{maxWidth: 200}}>` |
| `AspectRatio` | `<View style={{aspectRatio: 16/9}}>` |
| `Transform.rotate/scale/translate` | `<View style={{transform: [{rotate: '...'}]}}>` |
| `Spacer` | `<View style={{flex: 1}}>` |
| `FittedBox` | `resizeMode` or `adjustsFontSizeToFit` |
| `IntrinsicHeight` / `IntrinsicWidth` | Not available; use flex or explicit dimensions |
"""

API_PLATFORM_SECTION = """
## API & Platform

| Flutter | React Native |
|---------|-------------|
| `http.get(url)` / `http.post(url)` | `fetch(url)` |
| `SharedPreferences.getInstance()` | `AsyncStorage` from `@react-native-async-storage/async-storage` |
| `Platform.isIOS` / `Platform.isAndroid` | `Platform.OS === 'ios'` / `Platform.OS === 'android'` |
| `dart:convert jsonEncode/jsonDecode` | `JSON.stringify` / `JSON.parse` |
| `Timer` / `Timer.periodic` | `setTimeout` / `setInterval` |
| `Future.delayed(duration)` | `setTimeout(callback, ms)` |
| `intl` date formatting | `date-fns` or `Intl.DateTimeFormat` |
| `dart:io File` operations | `react-native-fs` |
| `MethodChannel` / `EventChannel` | `NativeModules` / `NativeEventEmitter` |
"""

# =============================================================================
# Per-category prompt builder
# =============================================================================

CATEGORY_SECTIONS: dict[str, list[str]] = {
    "screens": [WIDGET_MAPPING_SECTION, STATE_MANAGEMENT_SECTION, NAVIGATION_SECTION, STYLING_SECTION, LAYOUT_SECTION],
    "widgets": [WIDGET_MAPPING_SECTION, STYLING_SECTION, LAYOUT_SECTION],
    "services": [API_PLATFORM_SECTION],
    "models": [],
    "providers": [STATE_MANAGEMENT_SECTION],
    "utils": [API_PLATFORM_SECTION],
}


def build_category_system_prompt(category: str) -> str:
    """Build a system prompt with only the sections relevant to the given category."""
    sections = [FLUTTER_TO_RN_CORE]
    extra = CATEGORY_SECTIONS.get(category, [])
    sections.extend(extra)
    return "\n".join(sections)


# =============================================================================
# Full combined prompt (backward compatibility)
# =============================================================================

# Legacy alias — resolves to the "screens" category prompt (not a generic full prompt).
# New code should call build_category_system_prompt(category) instead.
FLUTTER_TO_RN_SYSTEM = build_category_system_prompt("screens")


# =============================================================================
# Prompt builder
# =============================================================================


def get_conversion_prompt(source_code: str, filename: str) -> str:
    """Build user prompt for Flutter-to-RN conversion."""
    return f"""Convert the following Flutter Dart code to React Native TypeScript/TSX code.

Source file: {filename}

```dart
{source_code}
```

Generate the React Native TypeScript/TSX code now."""

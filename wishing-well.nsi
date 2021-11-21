!include "MUI2.nsh"
!define MUI_ICON "icon.ico"

Name "Wishing Well"
OutFile "wishing-well-1.0.exe"
Unicode True
RequestExecutionLevel admin
InstallDir "$PROGRAMFILES\Wishing Well"
InstallDirRegKey HKLM "Software\WishingWell" "InstallDir"

;--------------------------------
; Pages

!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

;--------------------------------

!insertmacro MUI_LANGUAGE "English"

;--------------------------------
; Section

Section "Wishing Well"

  SectionIn RO
  SetOutPath $INSTDIR
  
  ; Files to install
  File /r "wishing-well.dist\frontend*.*"
  File "wishing-well.dist\icon.png"
  File "wishing-well.dist\wishing-well.exe"

  File /r "wishing-well.dist\tcl*.*"
  File /r "wishing-well.dist\tk*.*"
  File "wishing-well.dist\libcrypto-1_1.dll"
  File "wishing-well.dist\libssl-1_1.dll"
  File "wishing-well.dist\python39.dll"
  File "wishing-well.dist\vcruntime140.dll"
  File "wishing-well.dist\tcl86t.dll"
  File "wishing-well.dist\tk86t.dll"
  File "wishing-well.dist\_bz2.pyd"
  File "wishing-well.dist\_hashlib.pyd"
  File "wishing-well.dist\_lzma.pyd"
  File "wishing-well.dist\_socket.pyd"
  File "wishing-well.dist\_ssl.pyd"
  File "wishing-well.dist\_tkinter.pyd"
  File "wishing-well.dist\select.pyd"
  File "wishing-well.dist\unicodedata.pyd"
  
  ; Write the installation path into the registry
  WriteRegStr HKLM "Software\WishingWell" "InstallDir" "$INSTDIR"
  
  ; start menu shortcut
  CreateDirectory "$SMPROGRAMS\Wishing Well"
  CreateShortcut "$SMPROGRAMS\Wishing Well\Wishing Well.lnk" "$INSTDIR\wishing-well.exe"

  ; Write the uninstall keys for Windows
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\WishingWell" "DisplayName" "Wishing Well"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\WishingWell" "DisplayIcon" '"$INSTDIR\wishing-well.exe"'
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\WishingWell" "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\WishingWell" "NoModify" 1
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\WishingWell" "NoRepair" 1
  WriteUninstaller "$INSTDIR\uninstall.exe"
  
SectionEnd

;--------------------------------
; Uninstaller

Section "Uninstall"
  
  ; Remove registry keys
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\WishingWell"
  DeleteRegKey HKLM "Software\WishingWell"

  Delete "$SMPROGRAMS\Wishing Well\*.lnk"
  RMDir "$SMPROGRAMS\Wishing Well"
  RMDir /r "$INSTDIR"

SectionEnd

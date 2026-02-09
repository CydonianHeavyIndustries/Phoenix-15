import QtQuick 2.15
import QtQuick.Controls 2.15
import SddmComponents 2.0

Rectangle {
    width: Screen.width
    height: Screen.height
    color: "#070c14"

    Image {
        anchors.fill: parent
        source: "background.png"
        fillMode: Image.PreserveAspectCrop
    }

    Rectangle {
        anchors.fill: parent
        color: "#05080f"
        opacity: 0.35
    }

    Column {
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.topMargin: 36
        anchors.rightMargin: 48
        spacing: 6

        Text {
            text: "CHII"
            color: "#9ad8ff"
            font.pixelSize: 22
            font.bold: true
        }
        Text {
            text: "CYDONIAN HEAVY INDUSTRIES INC."
            color: "#89a7ba"
            font.pixelSize: 12
            letterSpacing: 1.1
        }
    }

    Text {
        text: "PHOENIX-15"
        color: "#b8f3ff"
        font.pixelSize: 34
        font.bold: true
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.verticalCenter: parent.verticalCenter
        anchors.verticalCenterOffset: -120
        opacity: 0.9
    }

    Rectangle {
        width: 560
        height: 220
        radius: 120
        color: "#0a1a26"
        border.color: "#2de0c7"
        border.width: 2
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.verticalCenter: parent.verticalCenter
        anchors.verticalCenterOffset: 140
        opacity: 0.92

        Login {
            anchors.centerIn: parent
        }
    }
}

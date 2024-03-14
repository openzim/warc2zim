/*
This script tries to return a PNG image based on the file path provided in the `path`
query parameter. If `path` is not set of contains potential dangerous characters, the
script simply says "HELLO".

This is a quick-and-dirty hack to generate varying content based on query parameter, for
exercising zimit/warc2zim behaviors.
*/
<?php
if(isset($_GET['path']) && !strstr($_GET['path'], '/') && !strstr($_GET['path'], '\\')) {
    header("Content-type: image/png");
    readfile($_GET['path']);
    exit();
} else {
    echo("HELLO");
}
?>

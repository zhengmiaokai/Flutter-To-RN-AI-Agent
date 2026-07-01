import 'package:flutter/material.dart';

class ListPage extends StatefulWidget {
  final String name;
  const ListPage({super.key, required this.name});

  @override
  State<StatefulWidget> createState() => ListPageState();
}

class ListPageState extends State<ListPage> {
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(widget.name)),
      body: Container(
        color: Colors.white,
        child: ListView.separated(
          itemCount: 20,
          separatorBuilder: (context, index) => Divider(height: 1),
          itemBuilder: (context, index) {
            return Container(
              height: 50,
              alignment: Alignment.centerLeft,
              padding: EdgeInsets.symmetric(horizontal: 20),
              child: GestureDetector(
                onTap: () => print('Row ${index+1}'),
                child: Text('Row ${index+1}'),
              ),
            );
          },
        ),
      )
    );
  }
}